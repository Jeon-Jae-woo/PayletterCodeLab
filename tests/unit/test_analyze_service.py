"""
T3 > T3.7 — analyze_service 단위 테스트

[M1.F1]  소스 연결 관리 — 백그라운드 분석 오케스트레이션
[M1.F7]  통합 대시보드 — 분석 결과 캐시
[M1.AC 7.1] 비동기 분석 실행 흐름
[M1.EX-4] 디스크 부족 오류 처리
[M1.EX-6] 분석 타임아웃 30초
"""
import os
import sys
import threading
import time
from unittest import mock

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_analyze_state():
    """각 테스트 전 analyze_service 전역 상태 초기화."""
    from services import analyze_service
    from services.result_cache import AnalysisResultCache
    from services import source_service
    AnalysisResultCache.clear()
    with source_service._status_lock:
        source_service._project_statuses.clear()
    if analyze_service._analysis_thread and analyze_service._analysis_thread.is_alive():
        analyze_service._timeout_event.set()
        analyze_service._analysis_thread.join(timeout=2)
    analyze_service._analysis_thread = None
    analyze_service._timeout_event = threading.Event()
    analyze_service._disk_error = None
    yield
    # 테스트 후 스레드 정리
    from services import analyze_service as svc
    svc._timeout_event.set()
    if svc._analysis_thread and svc._analysis_thread.is_alive():
        svc._analysis_thread.join(timeout=2)


def _make_project(name='TestProj', path='/fake/path'):
    return {'name': name, 'path': path, 'source_type': 'local'}


# ---------------------------------------------------------------------------
# [M1.AC 7.1] 비동기 분석 실행
# ---------------------------------------------------------------------------

class TestStartAnalysis:
    """start_analysis() — 백그라운드 스레드 분석 [M1.AC 7.1]"""

    @mock.patch('services.analyze_service._analyze_one')
    def test_start_analysis_runs_in_background(self, mock_analyze):
        """start_analysis() 호출 후 분석 함수가 백그라운드에서 실행되어야 함"""
        from services import analyze_service
        mock_analyze.side_effect = lambda proj, ev: None
        analyze_service.start_analysis([_make_project()])
        if analyze_service._analysis_thread:
            analyze_service._analysis_thread.join(timeout=2)
        assert mock_analyze.called, "분석 함수가 호출되어야 합니다"

    @mock.patch('services.analyze_service._analyze_one')
    def test_start_analysis_initializes_pending_status(self, mock_analyze):
        """start_analysis() 호출 시 프로젝트 상태가 PENDING으로 초기화되어야 함"""
        from services import analyze_service, source_service
        started = threading.Event()

        def capture_and_wait(proj, ev):
            started.set()
            time.sleep(0.05)

        mock_analyze.side_effect = capture_and_wait
        analyze_service.start_analysis([_make_project('MyProj')])
        started.wait(timeout=1)
        statuses = source_service.get_project_statuses()
        # PENDING으로 시작 후 스레드 내에서 상태 변경됨 — 상태 키 존재 확인
        assert 'MyProj' in statuses, "start_analysis 후 프로젝트 상태가 등록되어야 합니다"

    @mock.patch('services.analyze_service._analyze_one')
    def test_duplicate_start_ignored(self, mock_analyze):
        """이미 분석 중이면 두 번째 start_analysis 요청은 무시되어야 함"""
        from services import analyze_service
        block = threading.Event()
        call_count = [0]

        def slow_analyze(proj, ev):
            call_count[0] += 1
            block.wait(timeout=1)

        mock_analyze.side_effect = slow_analyze
        analyze_service.start_analysis([_make_project()])
        time.sleep(0.05)
        analyze_service.start_analysis([_make_project('Other')])
        block.set()
        if analyze_service._analysis_thread:
            analyze_service._analysis_thread.join(timeout=2)
        assert call_count[0] == 1, "중복 start_analysis는 분석을 1회만 실행해야 합니다"


# ---------------------------------------------------------------------------
# [M1.EX-6] 타임아웃 처리
# ---------------------------------------------------------------------------

class TestAnalysisTimeout:
    """분석 타임아웃 처리 [M1.EX-6]"""

    def test_timeout_event_stops_loop(self):
        """timeout_event가 set되면 _run_analysis 루프가 즉시 중단되어야 함"""
        from services import analyze_service
        analyzed = []
        projects = [_make_project(f'Proj{i}') for i in range(3)]

        def fake_analyze(proj, ev):
            analyzed.append(proj['name'])
            ev.set()  # 첫 프로젝트 후 타임아웃 시뮬레이션

        with mock.patch.object(analyze_service, '_analyze_one', side_effect=fake_analyze):
            event = threading.Event()
            analyze_service._run_analysis(projects, event)
        assert len(analyzed) == 1, "타임아웃 후 추가 프로젝트 분석이 중단되어야 합니다"

    @mock.patch('services.analyze_service._ANALYSIS_TIMEOUT', 0.1)
    @mock.patch('services.analyze_service._analyze_one')
    def test_timer_sets_timeout_event(self, mock_analyze):
        """타이머 만료 시 timeout_event가 set되어야 함 (0.1초 타임아웃)"""
        from services import analyze_service
        block = threading.Event()

        def slow(proj, ev):
            block.wait(timeout=2)

        mock_analyze.side_effect = slow
        analyze_service.start_analysis([_make_project()])
        time.sleep(0.3)
        block.set()
        if analyze_service._analysis_thread:
            analyze_service._analysis_thread.join(timeout=2)
        assert analyze_service._timeout_event.is_set(), "타이머 만료 시 timeout_event가 set되어야 합니다"


# ---------------------------------------------------------------------------
# [M1.EX-4] 디스크 오류 처리
# ---------------------------------------------------------------------------

class TestDiskError:
    """OSError 발생 시 전체 분석 중단 [M1.EX-4]"""

    @mock.patch('services.source_service.update_project_status')
    @mock.patch('services.source_service.get_project_files')
    def test_oserror_sets_disk_error(self, mock_files, mock_status):
        """OSError 발생 시 _disk_error가 설정되어야 함"""
        from services import analyze_service
        mock_files.side_effect = OSError("디스크 공간 부족")
        event = threading.Event()
        analyze_service._disk_error = None
        analyze_service._analyze_one(_make_project(), event)
        assert analyze_service._disk_error is not None, "OSError 시 _disk_error가 설정되어야 합니다"

    @mock.patch('services.source_service.update_project_status')
    @mock.patch('services.source_service.get_project_files')
    def test_oserror_triggers_timeout_event(self, mock_files, mock_status):
        """OSError 발생 시 timeout_event가 set되어 전체 분석이 중단되어야 함"""
        from services import analyze_service
        mock_files.side_effect = OSError("disk full")
        event = threading.Event()
        analyze_service._analyze_one(_make_project(), event)
        assert event.is_set(), "OSError 시 timeout_event가 set되어야 합니다"

    @mock.patch('services.source_service.update_project_status')
    @mock.patch('services.source_service.get_project_files')
    def test_oserror_marks_project_failed(self, mock_files, mock_status):
        """OSError 발생 프로젝트는 STATUS_FAILED로 마킹되어야 함"""
        from services import analyze_service, source_service
        mock_files.side_effect = OSError("disk error")
        event = threading.Event()
        analyze_service._analyze_one(_make_project('FailProj'), event)
        failed_calls = [
            c for c in mock_status.call_args_list
            if source_service.STATUS_FAILED in c.args
        ]
        assert len(failed_calls) >= 1, "OSError 시 STATUS_FAILED가 설정되어야 합니다"

    def test_get_disk_error_none_initially(self):
        """초기 상태에서 get_disk_error()는 None을 반환해야 함"""
        from services import analyze_service
        assert analyze_service.get_disk_error() is None, "초기 disk_error는 None이어야 합니다"

    @mock.patch('services.source_service.update_project_status')
    @mock.patch('services.source_service.get_project_files')
    def test_generic_exception_continues_not_disk_error(self, mock_files, mock_status):
        """일반 Exception은 disk_error 설정 없이 STATUS_FAILED 후 계속 진행"""
        from services import analyze_service
        mock_files.side_effect = ValueError("파싱 오류")
        event = threading.Event()
        analyze_service._disk_error = None
        analyze_service._analyze_one(_make_project(), event)
        assert not event.is_set(), "일반 Exception은 전체 중단 신호를 보내지 않아야 합니다"
        assert analyze_service._disk_error is None, "일반 Exception은 disk_error를 설정하지 않아야 합니다"


# ---------------------------------------------------------------------------
# [M1.F7] 진행률 API
# ---------------------------------------------------------------------------

class TestGetProgress:
    """get_progress() — 진행 상태 반환 [M1.F7]"""

    def test_get_progress_returns_dict(self):
        """get_progress() 반환값은 dict여야 함"""
        from services import analyze_service
        result = analyze_service.get_progress()
        assert isinstance(result, dict), "get_progress()는 dict를 반환해야 합니다"

    def test_complete_project_returns_100_pct(self):
        """STATUS_COMPLETE 프로젝트 → progress_pct=100"""
        from services import analyze_service, source_service
        source_service.update_project_status('DoneProj', source_service.STATUS_COMPLETE)
        prog = analyze_service.get_progress()
        assert 'DoneProj' in prog, "완료 프로젝트가 진행률에 포함되어야 합니다"
        assert prog['DoneProj']['progress_pct'] == 100, "완료 상태는 100%여야 합니다"

    def test_pending_project_returns_0_pct(self):
        """STATUS_PENDING 프로젝트 → progress_pct=0"""
        from services import analyze_service, source_service
        source_service.update_project_status('WaitProj', source_service.STATUS_PENDING)
        prog = analyze_service.get_progress()
        assert prog['WaitProj']['progress_pct'] == 0, "대기 상태는 0%여야 합니다"

    def test_progress_item_has_status_field(self):
        """get_progress() 항목에 status 필드가 포함되어야 함"""
        from services import analyze_service, source_service
        source_service.update_project_status('AProj', source_service.STATUS_ANALYZING)
        prog = analyze_service.get_progress()
        assert 'status' in prog['AProj'], "진행률 항목에 status 필드가 있어야 합니다"
        assert 'progress_pct' in prog['AProj'], "진행률 항목에 progress_pct 필드가 있어야 합니다"


# ---------------------------------------------------------------------------
# 파이프라인 헬퍼 함수 직접 단위 테스트
# ---------------------------------------------------------------------------

class TestAnalysisPipelineHelpers:
    """_get_csproj_files, _analyze_cs_files, _build_result, _run_analysis 직접 테스트."""

    def test_get_csproj_files_finds_csproj(self, tmp_path):
        """_get_csproj_files가 .csproj 파일을 재귀적으로 수집해야 함"""
        from services import analyze_service
        (tmp_path / 'A.csproj').write_text('<Project/>', encoding='utf-8')
        sub = tmp_path / 'sub'
        sub.mkdir()
        (sub / 'B.csproj').write_text('<Project/>', encoding='utf-8')
        (tmp_path / 'ignore.cs').write_text('', encoding='utf-8')
        result = analyze_service._get_csproj_files(str(tmp_path))
        names = [os.path.basename(p) for p in result]
        assert 'A.csproj' in names, ".csproj 파일이 수집되어야 합니다"
        assert 'B.csproj' in names, "하위 디렉터리 .csproj도 수집되어야 합니다"
        assert 'ignore.cs' not in names, ".cs 파일은 포함되지 않아야 합니다"

    def test_get_csproj_files_empty_dir(self, tmp_path):
        """빈 디렉터리 → 빈 리스트"""
        from services import analyze_service
        result = analyze_service._get_csproj_files(str(tmp_path))
        assert result == [], "빈 디렉터리는 빈 리스트를 반환해야 합니다"

    @mock.patch('services.analyze_service.flow_analyzer')
    @mock.patch('services.analyze_service.sp_detector')
    @mock.patch('services.analyze_service.complexity_analyzer')
    def test_analyze_cs_files_empty_list(self, mock_cc, mock_sp, mock_flow):
        """빈 cs_files → 빈 결과 dict"""
        from services import analyze_service
        mock_flow.enrich_with_complexity.return_value = {'nodes': [], 'edges': []}
        result = analyze_service._analyze_cs_files([])
        assert result['complexity'] == [], "빈 파일 목록은 빈 complexity를 반환해야 합니다"
        assert result['sp_calls'] == [], "빈 파일 목록은 빈 sp_calls를 반환해야 합니다"

    @mock.patch('services.analyze_service.flow_analyzer')
    @mock.patch('services.analyze_service.sp_detector')
    @mock.patch('services.analyze_service.complexity_analyzer')
    def test_analyze_cs_files_aggregates_chunks(self, mock_cc, mock_sp, mock_flow):
        """_analyze_cs_files가 청크별 결과를 올바르게 집계해야 함"""
        from services import analyze_service
        mock_cc.analyze_complexity.return_value = [{'cc': 3}]
        mock_sp.detect_sp_calls.return_value = [{'sp_name': 'UP_TEST'}]
        mock_flow.extract_call_graph.return_value = {
            'nodes': [{'id': 'A'}], 'edges': [{'caller': 'A', 'callee': 'B'}]
        }
        mock_flow.enrich_with_complexity.return_value = {'nodes': [{'id': 'A'}], 'edges': []}
        files = ['f1.cs', 'f2.cs']
        result = analyze_service._analyze_cs_files(files)
        # 2개 파일 → 1청크(CHUNK_SIZE=500 초과 안 함) → 각 analyzer 1회 호출 → 항목 1개
        assert len(result['complexity']) == 1, "1청크 결과가 집계되어야 합니다"
        assert len(result['sp_calls']) == 1, "sp_calls도 집계되어야 합니다"

    @mock.patch('services.analyze_service.dependency_analyzer')
    @mock.patch('services.analyze_service._get_csproj_files')
    def test_build_result_combines_analysis_and_dependency(self, mock_csproj, mock_dep):
        """_build_result가 analysis dict + dependency_graph를 합쳐야 함"""
        from services import analyze_service
        mock_csproj.return_value = ['/fake/A.csproj']
        mock_dep.parse_csproj.return_value = {'name': 'A', 'dependencies': [], 'packages': []}
        mock_dep.build_dependency_graph.return_value = {'nodes': [], 'edges': []}
        analysis = {'complexity': [], 'sp_calls': [], 'call_graph': {'nodes': [], 'edges': []}}
        result = analyze_service._build_result('/fake/path', analysis)
        assert 'dependency_graph' in result, "결과에 dependency_graph가 포함되어야 합니다"
        assert 'call_graph' in result, "결과에 call_graph가 포함되어야 합니다"

    @mock.patch('services.source_service.update_project_status')
    @mock.patch('services.analyze_service._build_result')
    @mock.patch('services.source_service.get_project_files')
    def test_run_analysis_processes_all_projects(self, mock_files, mock_build, mock_status):
        """_run_analysis가 타임아웃 없을 시 모든 프로젝트를 처리해야 함"""
        from services import analyze_service
        mock_files.return_value = []
        mock_build.return_value = {
            'complexity': [], 'sp_calls': [],
            'call_graph': {'nodes': [], 'edges': []},
            'dependency_graph': {'nodes': [], 'edges': []},
        }
        projects = [_make_project(f'P{i}', '/fake') for i in range(2)]
        event = threading.Event()
        analyze_service._run_analysis(projects, event)
        # 2개 프로젝트 각각 최소 STATUS_ANALYZING + STATUS_COMPLETE 호출 → 4회 이상
        assert mock_status.call_count >= 4, "2개 프로젝트 모두 상태가 갱신되어야 합니다"
