"""
GitLab 실제 어댑터 — production 환경 전용 [PR-3] EnvironmentDivergence

python-gitlab API 기반. 사설망 GitLab 서버에 Personal Access Token으로 인증.
사설 SSL 인증서 대응: verify_ssl=False 허용 (사용자 명시 동의 후) + 보안 경고 포함.
런타임 검증 deferred:production — 로컬에서는 GitLabMockClient로 대체.
"""
import io
import os
import ssl
import zipfile
from typing import List, Dict

from services.source_service import CACHE_SHA_FILENAME, SourceManager

# SSL 검증 비활성화 경고 문구 [M1.AC 1.7] — verify=False 선택 시 응답에 포함
_SSL_DISABLED_WARNING = "SSL 검증 비활성화 — 보안 위험 주의. 사설 인증서 환경에서만 사용하세요."


class GitLabClient(SourceManager):
    """
    GitLab REST API 어댑터. python-gitlab 라이브러리 사용.
    Token은 메모리에만 보관 — 로그/파일 기록 절대 금지 ([PR-6] 보안 정책).
    """

    def __init__(self):
        # _gl: python-gitlab Gitlab 인스턴스 (connect() 호출 시 초기화)
        self._gl = None
        # verify=False 사용 시 보안 경고 메시지 저장 — 라우트 레이어에서 응답에 포함
        self.ssl_warning: str = ''

    def connect(self, url: str = '', token: str = '', verify_ssl: bool = True, **kwargs) -> bool:
        """
        GitLab 서버 연결 + 인증.
        token은 로그에 절대 출력 금지 ([PR-6] Access Token 마스킹).
        verify_ssl=False: 사설 인증서 환경에서만 허용, 보안 경고 저장 [M1.AC 1.7].
        ssl.SSLError 감지 시 [M1.EX-10] 안내 메시지 포함 예외 발생.
        """
        import gitlab

        # SSL 검증 비활성화 경고 기록 — 라우트가 응답에 포함
        if not verify_ssl:
            self.ssl_warning = _SSL_DISABLED_WARNING

        self._gl = gitlab.Gitlab(url, private_token=token, ssl_verify=verify_ssl)
        try:
            self._gl.auth()
        except ssl.SSLError as exc:
            # [M1.EX-10] SSL 인증서 오류 — verify=False 옵션 안내
            raise ssl.SSLError(
                f"[M1.EX-10] GitLab SSL 인증서 오류: {exc}. "
                "verify_ssl=False 옵션을 설정하여 SSL 검증을 비활성화하거나 "
                "사설 인증서를 시스템에 등록하세요."
            ) from exc
        return True

    def list_projects(self) -> List[Dict[str, str]]:
        """GitLab 전체 프로젝트 목록 조회. connect() 선행 필수."""
        if self._gl is None:
            raise RuntimeError("list_projects() 호출 전 connect()가 필요합니다")
        projects = self._gl.projects.list(all=True)
        return [
            {'id': str(p.id), 'name': p.name, 'path': p.path_with_namespace}
            for p in projects
        ]

    def clone_project(self, project_id: str, target_dir: str) -> str:
        """
        GitLab ZIP 아카이브 다운로드 후 압축 해제 방식으로 클론. [PR-8]
        repository_archive() API 사용. SHA 파일 저장으로 캐시 유효성 지원 [M1.AC 1.5].
        """
        if self._gl is None:
            raise RuntimeError("clone_project() 호출 전 connect()가 필요합니다")
        project = self._gl.projects.get(int(project_id))
        archive_bytes = project.repository_archive(format='zip')
        os.makedirs(target_dir, exist_ok=True)
        _extract_zip_archive(archive_bytes, target_dir)
        # 최신 커밋 SHA 저장 — 캐시 유효성 검증용 [M1.AC 1.5]
        try:
            commits = project.commits.list(per_page=1)
            sha = commits[0].id if commits else ''
        except Exception:
            sha = ''
        _write_cache_sha(target_dir, sha)
        return target_dir


def _get_zip_root_prefix(members: list) -> str:
    """GitLab ZIP 최상위 디렉터리 접두어 반환 (예: 'project-main-sha/'). 없으면 빈 문자열."""
    if not members:
        return ''
    first = members[0]
    return first.split('/')[0] + '/' if '/' in first else ''


def _extract_zip_archive(archive_bytes: bytes, target_dir: str) -> None:
    """
    ZIP 아카이브를 target_dir에 압축 해제. [PR-8]
    GitLab ZIP 최상위 디렉터리(예: project-main-abc123/)를 제거하고 내용만 추출.
    TODO [T3 > R3-intra.2]: utils/file_utils.py로 공통화 예정.
    """
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        members = zf.namelist()
        if not members:
            return
        root_prefix = _get_zip_root_prefix(members)
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
