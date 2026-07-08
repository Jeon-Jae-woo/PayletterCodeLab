"""
SourceManager 포트 인터페이스 및 공통 모듈 — Port-Adapter 패턴 [GR-1.6]

GitLabClient, GitLabMockClient, GitHubClient, LocalFolderManager가 모두
SourceManager 인터페이스를 구현. Composition Root(app.py)에서 환경 변수에
따라 적절한 어댑터를 주입.

모듈 수준 공통 함수:
  get_cache_path()       — 클론 캐시 경로 생성 [PR-8]
  get_project_files()    — .cs 파일 목록 수집
  check_cache_valid()    — 커밋 SHA 비교로 캐시 유효성 검증 [M1.AC 1.5]
  update_project_status() — 분석 상태 스레드 세이프 갱신 [M1.AC 1.4]
  get_project_statuses() — 전체 상태 스냅샷 반환
"""
import os
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

# 캐시 SHA 파일명 상수 — check_cache_valid() 및 어댑터 clone 구현과 공유
CACHE_SHA_FILENAME = '.cache_sha'

# 프로젝트 분석 상태 상수 [M1.AC 1.4]
STATUS_PENDING = '대기 중'
STATUS_CLONING = '클론 중'
STATUS_ANALYZING = '분석 중'
STATUS_COMPLETE = '완료'
STATUS_FAILED = '실패'

# 스레드 세이프 프로젝트 상태 저장소
_status_lock = threading.Lock()
_project_statuses: Dict[str, str] = {}


def get_cache_path(source_type: str, project_name: str) -> str:
    """클론 캐시 경로 반환: temp/projects/{source_type}/{project_name}/ [PR-8]"""
    return os.path.join('temp', 'projects', source_type, project_name)


def get_project_files(project_path: str) -> List[str]:
    """프로젝트 경로에서 .cs 파일 목록을 재귀적으로 수집."""
    cs_files = []
    for root, _, files in os.walk(project_path):
        for fname in files:
            if fname.endswith('.cs'):
                cs_files.append(os.path.join(root, fname))
    return sorted(cs_files)


def check_cache_valid(project_path: str, remote_sha: str) -> bool:
    """
    캐시된 커밋 SHA와 원격 SHA를 비교. [M1.AC 1.5]
    일치하면 True(재클론 생략), 다르거나 캐시 없으면 False(재클론 필요).
    """
    sha_file = os.path.join(project_path, CACHE_SHA_FILENAME)
    if not os.path.exists(sha_file):
        return False
    try:
        with open(sha_file, 'r', encoding='utf-8') as f:
            cached_sha = f.read().strip()
        return cached_sha == remote_sha.strip()
    except OSError:
        return False


def update_project_status(project_name: str, status: str) -> None:
    """프로젝트 분석 상태 갱신 (스레드 세이프). [M1.AC 1.4]"""
    with _status_lock:
        _project_statuses[project_name] = status


def get_project_statuses() -> Dict[str, str]:
    """현재 전체 프로젝트 상태의 스냅샷(복사본)을 반환 (스레드 세이프)."""
    with _status_lock:
        return dict(_project_statuses)


class SourceManager(ABC):
    """소스 저장소 접근 포트 인터페이스. 구현체: GitLabClient, GitLabMockClient, GitHubClient, LocalFolderManager."""

    @abstractmethod
    def connect(self, **kwargs) -> bool:
        """소스에 연결. 성공 시 True, 실패 시 예외 또는 False 반환."""

    @abstractmethod
    def list_projects(self) -> List[Dict[str, str]]:
        """
        프로젝트 목록 반환.
        각 항목 구조: {'id': str, 'name': str, 'path': str}
        """

    @abstractmethod
    def clone_project(self, project_id: str, target_dir: str) -> str:
        """
        프로젝트를 target_dir에 클론/복사.
        반환값: 클론된 실제 경로 (str)
        """


class LocalFolderManager(SourceManager):
    """
    로컬 폴더 소스 어댑터 — 경로 유효성 검증 + 직접 참조 [PR-8]
    복사/클론 없이 지정된 폴더를 직접 분석 대상으로 등록.
    Path Traversal 방지: os.path.abspath() 정규화 + 존재/cs파일 검증 [PR-6]
    """

    def __init__(self) -> None:
        self._path: Optional[str] = None

    def connect(self, path: str = '', **kwargs) -> bool:
        """
        로컬 폴더 경로 유효성 검증. [M1.AC 1.3]
        os.path.abspath() 정규화 후 존재 여부 + .cs 파일 포함 여부 확인.
        존재하지 않거나 .cs 파일이 없으면 예외 발생 ([M1.EX-3]).
        """
        abs_path = os.path.abspath(path)
        if not os.path.isdir(abs_path):
            raise FileNotFoundError(
                f"[M1.EX-3] 유효한 C# 프로젝트 폴더가 아닙니다: {path}"
            )
        cs_files = get_project_files(abs_path)
        if not cs_files:
            raise ValueError(
                f"[M1.EX-3] 유효한 C# 프로젝트 폴더가 아닙니다: .cs 파일이 없습니다 ({path})"
            )
        self._path = abs_path
        return True

    def list_projects(self) -> List[Dict[str, str]]:
        """연결된 로컬 폴더를 단일 프로젝트로 반환."""
        if self._path is None:
            raise RuntimeError("list_projects() 호출 전 connect()가 필요합니다")
        return [
            {
                'id': self._path,
                'name': os.path.basename(self._path),
                'path': self._path,
            }
        ]

    def clone_project(self, project_id: str, target_dir: str) -> str:
        """
        로컬 폴더는 복사 없이 원본 경로를 직접 반환 [PR-8].
        connect() 시 이미 검증된 경로를 그대로 반환.
        """
        if self._path is None:
            raise RuntimeError("clone_project() 호출 전 connect()가 필요합니다")
        return self._path
