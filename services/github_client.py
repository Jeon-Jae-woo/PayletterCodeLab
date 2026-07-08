"""
GitHub 어댑터 — 로컬 환경 전용 [PR-3] EnvironmentDivergence

폐쇄망 PC(production)에서는 외부 인터넷 차단으로 GitHub 접근 불가.
폐쇄망 감지: api.github.com 연결 시도 10초 타임아웃 → [M1.EX-2] 처리.
GITHUB_DISABLED=true 환경 변수로 명시적 비활성화 가능 (config-externalize 계약).
"""
import io
import os
import socket
import urllib.request
import zipfile
from typing import List, Dict

from services.source_service import CACHE_SHA_FILENAME, SourceManager

# 폐쇄망 감지 타임아웃 (초) — [M1.EX-2]
_NETWORK_CHECK_TIMEOUT = 10


class GitHubClient(SourceManager):
    """
    GitHub REST API 어댑터. PyGithub 라이브러리 사용.
    Token은 메모리에만 보관 — 로그/파일 기록 절대 금지 ([PR-6] 보안 정책).
    """

    def __init__(self):
        self._gh = None

    def connect(self, token: str = '', **kwargs) -> bool:
        """
        GitHub API 연결. 폐쇄망 감지 선행.
        [M1.EX-2]: 네트워크 차단 감지 시 ConnectionError 발생.
        """
        if not self._check_network():
            raise ConnectionError(
                "[M1.EX-2] GitHub API 접근 불가 — 폐쇄망 환경에서 외부 인터넷 차단. "
                "로컬 폴더 소스 유형으로 전환하거나 GITHUB_DISABLED=true를 설정하세요."
            )
        from github import Github
        self._gh = Github(token) if token else Github()
        return True

    def list_projects(self) -> List[Dict[str, str]]:
        """GitHub 저장소 목록 조회. connect() 선행 필수."""
        if self._gh is None:
            raise RuntimeError("list_projects() 호출 전 connect()가 필요합니다")
        from services.source_service import get_cache_path
        repos = self._gh.get_user().get_repos()
        return [
            {
                'id': str(r.id),
                'name': r.name,
                # path는 로컬 클론 캐시 경로 — analyze_service가 직접 사용
                'path': get_cache_path('github', r.name),
                'source_type': 'github',
            }
            for r in repos
        ]

    def clone_project(self, project_id: str, target_dir: str) -> str:
        """
        GitHub ZIP 다운로드 후 압축 해제 방식으로 클론. [PR-8]
        PyGithub get_archive_link() + urllib.request로 ZIP 수신.
        SHA 파일 저장으로 캐시 유효성 지원 [M1.AC 1.5].
        """
        if self._gh is None:
            raise RuntimeError("clone_project() 호출 전 connect()가 필요합니다")
        repo = self._gh.get_repo(int(project_id))
        sha = repo.get_branch(repo.default_branch).commit.sha
        zip_url = repo.get_archive_link('zipball')
        with urllib.request.urlopen(zip_url) as response:
            archive_bytes = response.read()
        os.makedirs(target_dir, exist_ok=True)
        _extract_zip_archive(archive_bytes, target_dir)
        _write_cache_sha(target_dir, sha)
        return target_dir

    def _check_network(self, timeout: int = _NETWORK_CHECK_TIMEOUT) -> bool:
        """
        폐쇄망 감지 — api.github.com 포트 443 연결 시도.
        ConnectionError/OSError 발생 시 폐쇄망으로 판정.
        """
        try:
            with socket.create_connection(("api.github.com", 443), timeout=timeout):
                pass
            return True
        except (OSError, ConnectionError):
            return False


def _extract_zip_archive(archive_bytes: bytes, target_dir: str) -> None:
    """
    ZIP 아카이브를 target_dir에 압축 해제. [PR-8]
    GitHub ZIP 최상위 디렉터리(예: org-repo-sha7/)를 제거하고 내용만 추출.
    TODO [T3 > R3-intra.2]: utils/file_utils.py로 공통화 예정.
    """
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        members = zf.namelist()
        if not members:
            return
        first = members[0]
        root_prefix = first.split('/')[0] + '/' if '/' in first else ''
        for member in members:
            if member == root_prefix:
                continue
            relative = member[len(root_prefix):]
            if not relative:
                continue
            target_path = os.path.join(target_dir, relative)
            if member.endswith('/'):
                os.makedirs(target_path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with zf.open(member) as src, open(target_path, 'wb') as dst:
                    dst.write(src.read())


def _write_cache_sha(project_dir: str, sha: str) -> None:
    """SHA를 .cache_sha 파일에 저장 — check_cache_valid()와 대응. [M1.AC 1.5]"""
    sha_file = os.path.join(project_dir, CACHE_SHA_FILENAME)
    with open(sha_file, 'w', encoding='utf-8') as f:
        f.write(sha)
