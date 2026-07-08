"""
비동기 분석 오케스트레이션 서비스 — [M1.F1], [M1.F7]
"""
import logging
import os
import sys
import threading
from typing import List, Optional

from analyzers import complexity_analyzer, dependency_analyzer, flow_analyzer, sp_detector
from services import source_service
from services.result_cache import AnalysisResultCache

logger = logging.getLogger(__name__)

# 전체 분석 타임아웃 상수 — 30초 [M1.EX-6]
_ANALYSIS_TIMEOUT = 30
# 대용량 프로젝트 청크 크기 — 500개 파일 기준 배치 분할 [PR-3]
_CHUNK_SIZE = 500

_analysis_thread: Optional[threading.Thread] = None
_timeout_event: threading.Event = threading.Event()
_disk_error: Optional[str] = None
_lock = threading.Lock()


def _get_csproj_files(project_path: str) -> List[str]:
    """프로젝트 경로에서 .csproj 파일 목록을 재귀적으로 수집."""
    result = []
    for root, _, files in os.walk(project_path):
        for fname in files:
            if fname.endswith('.csproj'):
                result.append(os.path.join(root, fname))
    return result


def _analyze_cs_files(cs_files: List[str]) -> dict:
    """청크 분할 기반 .cs 파일 분석 → 복잡도/SP/호출 그래프 결과 dict.

    _CHUNK_SIZE 단위로 배치 처리하여 대용량 프로젝트 메모리 피크를 낮춘다.
    """
    complexity: list = []
    sp_calls: list = []
    nodes: list = []
    edges: list = []
    for i in range(0, len(cs_files), _CHUNK_SIZE):
        chunk = cs_files[i:i + _CHUNK_SIZE]
        complexity.extend(complexity_analyzer.analyze_complexity(chunk))
        sp_calls.extend(sp_detector.detect_sp_calls(chunk))
        chunk_graph = flow_analyzer.extract_call_graph(chunk)
        nodes.extend(chunk_graph.get('nodes', []))
        edges.extend(chunk_graph.get('edges', []))
    raw_graph = {'nodes': nodes, 'edges': edges}
    return {
        'complexity': complexity,
        'sp_calls': sp_calls,
        'call_graph': flow_analyzer.enrich_with_complexity(raw_graph, complexity),
    }


def _build_result(path: str, analysis: dict) -> dict:
    """분석 결과 dict 조합 — dependency_graph 추가."""
    csproj_files = _get_csproj_files(path)
    projects_info = [dependency_analyzer.parse_csproj(f) for f in csproj_files]
    return {
        'complexity': analysis['complexity'],
        'sp_calls': analysis['sp_calls'],
        'call_graph': analysis['call_graph'],
        'dependency_graph': dependency_analyzer.build_dependency_graph(projects_info),
    }


def _handle_disk_error(proj_name: str, exc: OSError, timeout_event: threading.Event) -> None:
    """디스크 공간 부족 등 I/O 오류 처리 — _disk_error 설정 후 전체 분석 중단 [M1.EX-4]."""
    global _disk_error
    with _lock:
        _disk_error = str(exc)
    source_service.update_project_status(proj_name, source_service.STATUS_FAILED)
    logger.error('analyze_service: 디스크 오류 — 전체 중단 | project=%s | error=%s',
                 proj_name, type(exc).__name__)
    timeout_event.set()


def _clone_github_if_needed(project: dict) -> str:
    """GitHub 프로젝트 클론 처리.

    source_type='github'인 경우 로컬 캐시 경로에 클론이 없으면 클론을 수행한다.
    캐시가 이미 존재하면 재클론 생략 [M1.AC 1.5].
    반환값: 분석에 사용할 로컬 경로.
    """
    if project.get('source_type') != 'github':
        return project.get('path', '')
    path = project.get('path', '')
    # 캐시 유효성 확인 — .cs 파일이 이미 존재하면 재클론 생략
    if os.path.isdir(path) and source_service.get_project_files(path):
        return path
    # 순환 임포트 방지: 함수 내부 지연 임포트
    from routes.source_routes import get_github_adapter
    adapter = get_github_adapter()
    if adapter is None:
        raise RuntimeError("GitHub 어댑터가 초기화되지 않았습니다. 소스 연결 화면에서 다시 연결하세요.")
    adapter.clone_project(project['id'], path)
    return path


def _analyze_one(project: dict, timeout_event: threading.Event) -> None:
    """단일 프로젝트 전체 분석 파이프라인.

    GitHub 프로젝트: STATUS_CLONING → clone → STATUS_ANALYZING → analyze.
    OSError(디스크 오류) → _handle_disk_error() + 전체 중단 신호 [M1.EX-4].
    일반 Exception → STATUS_FAILED 후 다음 프로젝트 계속 진행 [PR-8].
    """
    proj_name = project.get('name', 'unknown')
    try:
        # GitHub 클론 단계 (로컬/GitLab은 이미 경로 존재)
        if project.get('source_type') == 'github':
            source_service.update_project_status(proj_name, source_service.STATUS_CLONING)
        path = _clone_github_if_needed(project)
        source_service.update_project_status(proj_name, source_service.STATUS_ANALYZING)
        cs_files = source_service.get_project_files(path)
        if timeout_event.is_set():
            return
        result = _build_result(path, _analyze_cs_files(cs_files))
        AnalysisResultCache.set_results(proj_name, result)
        source_service.update_project_status(proj_name, source_service.STATUS_COMPLETE)
        logger.info('analyze_service: 완료 | project=%s | files=%d', proj_name, len(cs_files))
    except OSError as exc:
        _handle_disk_error(proj_name, exc, timeout_event)
    except Exception as exc:
        source_service.update_project_status(proj_name, source_service.STATUS_FAILED)
        logger.warning('analyze_service: 프로젝트 분석 실패 — 계속 | project=%s | error=%s',
                       proj_name, type(exc).__name__)


def _run_analysis(projects: list, timeout_event: threading.Event) -> None:
    """백그라운드 분석 루프 — 타임아웃 이벤트 감지 시 즉시 중단.

    sys.setrecursionlimit으로 _dfs 깊은 의존성 체인 RecursionError 방어.
    """
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 5000))
    for project in projects:
        if timeout_event.is_set():
            logger.warning('analyze_service: 타임아웃 또는 오류로 분석 루프 중단')
            break
        _analyze_one(project, timeout_event)


def _create_analysis_thread(
    projects: list, event: threading.Event, timer: threading.Timer
) -> threading.Thread:
    """타이머 + 분석 루프를 감싸는 데몬 스레드 생성 및 시작 [M1.EX-6]."""
    def _run():
        timer.start()
        try:
            _run_analysis(projects, event)
        finally:
            timer.cancel()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread


def start_analysis(selected_projects: list) -> None:
    """백그라운드 스레드에서 비동기 분석 시작 — [M1.AC 7.1].

    이미 분석 중이면 요청 무시. 타이머로 _ANALYSIS_TIMEOUT초 후 중단 [M1.EX-6].
    """
    global _analysis_thread, _timeout_event, _disk_error
    with _lock:
        if _analysis_thread is not None and _analysis_thread.is_alive():
            logger.warning('analyze_service: 이미 분석 진행 중 — 요청 무시')
            return
        _disk_error = None
        _timeout_event = threading.Event()
        for proj in selected_projects:
            source_service.update_project_status(
                proj.get('name', 'unknown'), source_service.STATUS_PENDING
            )
        event = _timeout_event
        timer = threading.Timer(_ANALYSIS_TIMEOUT, event.set)
        timer.daemon = True
        _analysis_thread = _create_analysis_thread(selected_projects, event, timer)


def get_progress() -> dict:
    """분석 진행 상태 반환 — {project_name: {status, progress_pct}} [M1.F7]"""
    statuses = source_service.get_project_statuses()
    result = {}
    for name, status in statuses.items():
        if status == source_service.STATUS_COMPLETE:
            pct = 100
        elif status == source_service.STATUS_PENDING:
            pct = 0
        else:
            pct = 50
        result[name] = {'status': status, 'progress_pct': pct}
    return result


def get_disk_error() -> Optional[str]:
    """디스크 오류 메시지 반환. None이면 오류 없음 [M1.EX-4]."""
    with _lock:
        return _disk_error
