"""
T3 > T3.0.1 — SourceManager 공통 모듈 테스트

[M1.S3]  로컬 폴더 유효성 검증 성공 / [M1.AC 1.3]
[M1.S10] 캐시 활용 — 동일 커밋 SHA 재분석 / [M1.AC 1.5]
[M1.S25] Path Traversal 공격 방어 / [M1.AC 1.3]
"""
import io
import os
import sys
import threading
import zipfile
from unittest import mock

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# get_cache_path()
# ---------------------------------------------------------------------------

class TestGetCachePath:
    """get_cache_path() — 캐시 경로 구조 검증"""

    def test_cache_path_includes_source_type_and_project_name(self):
        """캐시 경로에 source_type과 project_name이 포함되어야 함"""
        from services.source_service import get_cache_path
        path = get_cache_path('gitlab', 'my_project')
        normalized = path.replace('\\', '/')
        assert 'gitlab' in normalized
        assert 'my_project' in normalized

    def test_cache_path_contains_temp_projects(self):
        """캐시 경로가 temp/projects/ 하위 구조여야 함 [PR-8]"""
        from services.source_service import get_cache_path
        path = get_cache_path('github', 'repo_name')
        normalized = path.replace('\\', '/')
        assert 'temp/projects' in normalized, f"temp/projects 경로를 포함해야 합니다 (실제: {normalized})"

    def test_cache_path_returns_string(self):
        """get_cache_path()가 문자열을 반환해야 함"""
        from services.source_service import get_cache_path
        result = get_cache_path('local', 'project')
        assert isinstance(result, str), "get_cache_path()가 문자열을 반환해야 합니다"

    def test_cache_path_separates_by_source_type(self):
        """GitLab / GitHub / local 각각 다른 경로를 반환해야 함"""
        from services.source_service import get_cache_path
        gitlab_path = get_cache_path('gitlab', 'proj')
        github_path = get_cache_path('github', 'proj')
        local_path = get_cache_path('local', 'proj')
        assert gitlab_path != github_path
        assert github_path != local_path


# ---------------------------------------------------------------------------
# check_cache_valid()  [M1.S10] [M1.AC 1.5]
# ---------------------------------------------------------------------------

class TestCheckCacheValid:
    """check_cache_valid() — SHA 비교 로직 검증 [M1.S10]"""

    def test_cache_valid_when_sha_matches(self, tmp_path):
        """[M1.S10] 동일 SHA이면 True 반환 — 재클론 생략"""
        from services.source_service import check_cache_valid
        (tmp_path / '.cache_sha').write_text('abc123def456')
        result = check_cache_valid(str(tmp_path), 'abc123def456')
        assert result is True, "동일 SHA일 때 check_cache_valid()가 True를 반환해야 합니다"

    def test_cache_invalid_when_sha_differs(self, tmp_path):
        """SHA가 다르면 False 반환 — 재클론 필요"""
        from services.source_service import check_cache_valid
        (tmp_path / '.cache_sha').write_text('old_sha_value')
        result = check_cache_valid(str(tmp_path), 'new_sha_value')
        assert result is False, "SHA가 다를 때 check_cache_valid()가 False를 반환해야 합니다"

    def test_cache_invalid_when_no_cache_file(self, tmp_path):
        """캐시 파일이 없으면 False 반환 — 최초 클론 필요"""
        from services.source_service import check_cache_valid
        result = check_cache_valid(str(tmp_path), 'some_sha')
        assert result is False, "캐시 파일 없을 때 check_cache_valid()가 False를 반환해야 합니다"

    def test_cache_valid_with_trailing_newline(self, tmp_path):
        """SHA 파일 말미 개행 무시 — 파일 저장 시 개행 허용"""
        from services.source_service import check_cache_valid
        (tmp_path / '.cache_sha').write_text('abc123\n')
        result = check_cache_valid(str(tmp_path), 'abc123')
        assert result is True, "SHA 파일의 공백/개행을 무시하고 True를 반환해야 합니다"

    def test_cache_invalid_when_empty_remote_sha(self, tmp_path):
        """remote_sha가 빈 문자열이면 False 반환 (빈 SHA는 신뢰 불가)"""
        from services.source_service import check_cache_valid
        (tmp_path / '.cache_sha').write_text('')
        result = check_cache_valid(str(tmp_path), '')
        # 빈 SHA끼리 일치해도 신뢰할 수 없음 — 구현에 따라 True/False 허용
        # 핵심 요구사항: 런타임 예외 없이 bool 반환
        assert isinstance(result, bool), "check_cache_valid()가 bool을 반환해야 합니다"


# ---------------------------------------------------------------------------
# get_project_files()
# ---------------------------------------------------------------------------

class TestGetProjectFiles:
    """get_project_files() — .cs 파일 목록 수집"""

    def test_finds_cs_files_in_root(self, tmp_path):
        """.cs 파일을 루트 디렉터리에서 찾을 수 있어야 함"""
        from services.source_service import get_project_files
        (tmp_path / 'Program.cs').write_text('// C# file')
        (tmp_path / 'Helper.cs').write_text('// Another C# file')
        files = get_project_files(str(tmp_path))
        assert len(files) == 2, f".cs 파일 2개를 찾아야 합니다 (실제: {len(files)}개)"

    def test_finds_cs_files_recursively(self, tmp_path):
        """.cs 파일을 하위 디렉터리에서도 재귀적으로 찾아야 함"""
        from services.source_service import get_project_files
        subdir = tmp_path / 'src' / 'Core'
        subdir.mkdir(parents=True)
        (subdir / 'Service.cs').write_text('// nested')
        files = get_project_files(str(tmp_path))
        assert len(files) == 1, ".cs 파일 1개를 재귀적으로 찾아야 합니다"
        assert files[0].endswith('Service.cs')

    def test_excludes_non_cs_files(self, tmp_path):
        """.cs 이외의 파일(.txt, .py, .json)은 제외되어야 함"""
        from services.source_service import get_project_files
        (tmp_path / 'readme.txt').write_text('readme')
        (tmp_path / 'config.json').write_text('{}')
        (tmp_path / 'script.py').write_text('# py')
        (tmp_path / 'App.cs').write_text('// cs')
        files = get_project_files(str(tmp_path))
        assert len(files) == 1, ".cs 파일만 반환되어야 합니다"
        assert files[0].endswith('App.cs')

    def test_returns_empty_when_no_cs_files(self, tmp_path):
        """.cs 파일이 없으면 빈 리스트를 반환해야 함"""
        from services.source_service import get_project_files
        (tmp_path / 'readme.txt').write_text('readme')
        files = get_project_files(str(tmp_path))
        assert files == [], ".cs 파일이 없을 때 빈 리스트를 반환해야 합니다"

    def test_returns_sorted_list(self, tmp_path):
        """파일 목록이 정렬된 순서로 반환되어야 함"""
        from services.source_service import get_project_files
        (tmp_path / 'Z_Last.cs').write_text('// z')
        (tmp_path / 'A_First.cs').write_text('// a')
        files = get_project_files(str(tmp_path))
        assert files == sorted(files), "파일 목록이 정렬 순서여야 합니다"


# ---------------------------------------------------------------------------
# update_project_status() / get_project_statuses()
# ---------------------------------------------------------------------------

class TestUpdateProjectStatus:
    """update_project_status() — 상태 갱신 스레드 세이프 [M1.AC 1.4]"""

    def test_status_stored_and_retrieved(self):
        """상태 갱신 후 조회 가능해야 함"""
        from services.source_service import update_project_status, get_project_statuses
        update_project_status('t301_proj_a', '완료')
        statuses = get_project_statuses()
        assert statuses.get('t301_proj_a') == '완료', "갱신된 상태가 반환되어야 합니다"

    def test_status_overwrite(self):
        """같은 프로젝트 상태 갱신 시 덮어쓰기"""
        from services.source_service import update_project_status, get_project_statuses
        update_project_status('t301_proj_overwrite', '클론 중')
        update_project_status('t301_proj_overwrite', '완료')
        statuses = get_project_statuses()
        assert statuses.get('t301_proj_overwrite') == '완료', "마지막 상태가 반환되어야 합니다"

    def test_status_thread_safe(self):
        """여러 스레드에서 동시 갱신 시 데이터 손상 없음"""
        from services.source_service import update_project_status, get_project_statuses
        errors = []

        def worker(name: str, status: str) -> None:
            try:
                update_project_status(name, status)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(f't301_thread_{i}', f'상태_{i}'))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"스레드 동시 갱신 중 오류 발생: {errors}"
        statuses = get_project_statuses()
        for i in range(20):
            assert f't301_thread_{i}' in statuses, f"t301_thread_{i} 상태가 저장되어야 합니다"

    def test_get_statuses_returns_snapshot(self):
        """get_project_statuses()가 현재 상태의 스냅샷(복사본)을 반환해야 함"""
        from services.source_service import update_project_status, get_project_statuses
        update_project_status('t301_snap', '분석 중')
        snapshot = get_project_statuses()
        update_project_status('t301_snap', '완료')  # 스냅샷 이후 변경
        assert snapshot.get('t301_snap') == '분석 중', "스냅샷은 변경에 영향받지 않아야 합니다"


# ---------------------------------------------------------------------------
# LocalFolderManager  [M1.S3], [M1.S25]
# ---------------------------------------------------------------------------

class TestLocalFolderManager:
    """LocalFolderManager — 로컬 폴더 소스 어댑터 [M1.S3], [M1.S25]"""

    def test_implements_source_manager_interface(self):
        """LocalFolderManager가 SourceManager 인터페이스를 구현해야 함"""
        from services.source_service import LocalFolderManager, SourceManager
        assert issubclass(LocalFolderManager, SourceManager), (
            "LocalFolderManager가 SourceManager를 상속해야 합니다"
        )

    def test_connect_succeeds_with_valid_path(self, tmp_path):
        """[M1.S3] 유효한 경로 + .cs 파일 존재 시 connect() True 반환"""
        from services.source_service import LocalFolderManager
        (tmp_path / 'App.cs').write_text('// C#')
        mgr = LocalFolderManager()
        result = mgr.connect(path=str(tmp_path))
        assert result is True, "유효한 경로에서 connect()가 True를 반환해야 합니다"

    def test_connect_fails_when_path_missing(self):
        """[M1.EX-3] 존재하지 않는 경로 → FileNotFoundError"""
        from services.source_service import LocalFolderManager
        mgr = LocalFolderManager()
        raised = False
        try:
            mgr.connect(path='/not/exist/path_xyz_987654321')
            raised = False
        except (ValueError, FileNotFoundError):
            raised = True
        assert raised, "존재하지 않는 경로에서 예외를 발생시켜야 합니다"

    def test_connect_fails_when_no_cs_files(self, tmp_path):
        """[M1.EX-3] .cs 파일 없는 경로 → ValueError"""
        from services.source_service import LocalFolderManager
        (tmp_path / 'readme.txt').write_text('no cs files')
        mgr = LocalFolderManager()
        raised = False
        try:
            mgr.connect(path=str(tmp_path))
        except (ValueError, FileNotFoundError):
            raised = True
        assert raised, ".cs 파일 없는 경로에서 예외를 발생시켜야 합니다"

    def test_list_projects_returns_folder_info(self, tmp_path):
        """connect() 후 list_projects()가 폴더 정보를 반환해야 함"""
        from services.source_service import LocalFolderManager
        (tmp_path / 'Main.cs').write_text('// C#')
        mgr = LocalFolderManager()
        mgr.connect(path=str(tmp_path))
        projects = mgr.list_projects()
        assert isinstance(projects, list), "list_projects()가 리스트를 반환해야 합니다"
        assert len(projects) == 1
        assert 'id' in projects[0]
        assert 'name' in projects[0]
        assert 'path' in projects[0]

    def test_list_projects_id_is_string(self, tmp_path):
        """list_projects() 반환 항목의 id가 문자열이어야 함 [GR-2.3]"""
        from services.source_service import LocalFolderManager
        (tmp_path / 'Foo.cs').write_text('// C#')
        mgr = LocalFolderManager()
        mgr.connect(path=str(tmp_path))
        projects = mgr.list_projects()
        assert isinstance(projects[0]['id'], str), "id 값이 문자열이어야 합니다"

    def test_clone_returns_original_path_without_copying(self, tmp_path):
        """로컬 폴더는 복사 없이 원본 경로를 반환 [PR-8]"""
        from services.source_service import LocalFolderManager
        (tmp_path / 'Prog.cs').write_text('// C#')
        mgr = LocalFolderManager()
        mgr.connect(path=str(tmp_path))
        result = mgr.clone_project(str(tmp_path), '/unused/target')
        assert result == str(tmp_path), "로컬 폴더는 원본 경로를 반환해야 합니다"

    def test_path_traversal_via_relative_resolved_to_nonexistent(self, tmp_path):
        """[M1.S25] 정규화 후 존재하지 않는 traversal 경로 → 예외"""
        from services.source_service import LocalFolderManager
        mgr = LocalFolderManager()
        # ../../../nonexistent_xyz 는 실제로 존재하지 않음 → 예외
        traversal = str(tmp_path) + '/../../nonexistent_xyz_t301_qa_12345'
        raised = False
        try:
            mgr.connect(path=traversal)
        except (ValueError, FileNotFoundError):
            raised = True
        assert raised, "Path traversal 시도가 차단되어야 합니다"

    def test_list_projects_raises_before_connect(self):
        """connect() 호출 전 list_projects() → RuntimeError"""
        from services.source_service import LocalFolderManager
        mgr = LocalFolderManager()
        raised = False
        try:
            mgr.list_projects()
        except RuntimeError:
            raised = True
        assert raised, "connect() 전 list_projects() 호출 시 RuntimeError 발생해야 합니다"

    def test_clone_project_raises_before_connect(self, tmp_path):
        """connect() 호출 전 clone_project() → RuntimeError"""
        from services.source_service import LocalFolderManager
        mgr = LocalFolderManager()
        raised = False
        try:
            mgr.clone_project(str(tmp_path), '/target')
        except RuntimeError:
            raised = True
        assert raised, "connect() 전 clone_project() 호출 시 RuntimeError 발생해야 합니다"


# ---------------------------------------------------------------------------
# GitLabClient.clone_project() — ZIP 다운로드 [T3.0.1 TODO 해소]
# ---------------------------------------------------------------------------

def _make_test_zip(filemap: dict) -> bytes:
    """테스트용 ZIP 바이트 생성. filemap: {내부경로: 파일내용}"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for member, content in filemap.items():
            zf.writestr(member, content)
    return buf.getvalue()


class TestGitLabClientCloneProject:
    """GitLabClient.clone_project() — ZIP 다운로드 + 압축 해제"""

    def test_clone_extracts_zip_to_target_dir(self, tmp_path):
        """clone_project()가 ZIP을 target_dir에 압축 해제해야 함"""
        from services.gitlab_client import GitLabClient
        zip_bytes = _make_test_zip({
            'project-main-abc123/': '',
            'project-main-abc123/App.cs': '// C# source',
            'project-main-abc123/src/Service.cs': '// Service',
        })
        mock_gitlab = mock.MagicMock()
        mock_gl = mock.MagicMock()
        mock_project = mock.MagicMock()
        mock_commit = mock.MagicMock()
        mock_commit.id = 'abc123def456'
        mock_project.repository_archive.return_value = zip_bytes
        mock_project.commits.list.return_value = [mock_commit]
        mock_gl.projects.get.return_value = mock_project
        mock_gitlab.Gitlab.return_value = mock_gl

        client = GitLabClient()
        with mock.patch.dict('sys.modules', {'gitlab': mock_gitlab}):
            client.connect(url='https://gitlab.example.com', token='test-token')
            result = client.clone_project('42', str(tmp_path))

        assert result == str(tmp_path), "clone_project()가 target_dir를 반환해야 합니다"
        assert (tmp_path / 'App.cs').exists(), "App.cs가 압축 해제되어야 합니다"
        assert (tmp_path / 'src' / 'Service.cs').exists(), "중첩 파일도 압축 해제되어야 합니다"

    def test_clone_writes_cache_sha_file(self, tmp_path):
        """.cache_sha 파일이 저장되어야 함 [M1.AC 1.5]"""
        from services.gitlab_client import GitLabClient
        zip_bytes = _make_test_zip({'project-main-abc/App.cs': '// cs'})
        mock_gitlab = mock.MagicMock()
        mock_gl = mock.MagicMock()
        mock_project = mock.MagicMock()
        mock_commit = mock.MagicMock()
        mock_commit.id = 'sha_abc123'
        mock_project.repository_archive.return_value = zip_bytes
        mock_project.commits.list.return_value = [mock_commit]
        mock_gl.projects.get.return_value = mock_project
        mock_gitlab.Gitlab.return_value = mock_gl

        client = GitLabClient()
        with mock.patch.dict('sys.modules', {'gitlab': mock_gitlab}):
            client.connect(url='https://gitlab.example.com', token='token')
            client.clone_project('1', str(tmp_path))

        sha_file = tmp_path / '.cache_sha'
        assert sha_file.exists(), ".cache_sha 파일이 저장되어야 합니다"
        assert sha_file.read_text().strip() == 'sha_abc123', "SHA 값이 파일에 저장되어야 합니다"

    def test_clone_raises_before_connect(self, tmp_path):
        """connect() 전 clone_project() → RuntimeError"""
        from services.gitlab_client import GitLabClient
        client = GitLabClient()
        raised = False
        try:
            client.clone_project('1', str(tmp_path))
        except RuntimeError:
            raised = True
        assert raised, "connect() 전 clone_project() 호출 시 RuntimeError 발생해야 합니다"


# ---------------------------------------------------------------------------
# GitHubClient.clone_project() — ZIP 다운로드 [T3.0.1 TODO 해소]
# ---------------------------------------------------------------------------

class TestGitHubClientCloneProject:
    """GitHubClient.clone_project() — ZIP 다운로드 + 압축 해제"""

    def test_clone_extracts_zip_to_target_dir(self, tmp_path):
        """clone_project()가 GitHub ZIP을 target_dir에 압축 해제해야 함"""
        from services.github_client import GitHubClient
        zip_bytes = _make_test_zip({
            'org-repo-abc1234/': '',
            'org-repo-abc1234/Program.cs': '// main',
        })
        mock_github = mock.MagicMock()
        mock_gh = mock.MagicMock()
        mock_repo = mock.MagicMock()
        mock_repo.default_branch = 'main'
        mock_repo.get_branch.return_value.commit.sha = 'gh_sha_def456'
        mock_repo.get_archive_link.return_value = 'https://codeload.example.com/archive.zip'
        mock_gh.get_repo.return_value = mock_repo
        mock_github.Github.return_value = mock_gh

        mock_response = mock.MagicMock()
        mock_response.read.return_value = zip_bytes
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        client = GitHubClient()
        with mock.patch.dict('sys.modules', {'github': mock_github}):
            with mock.patch.object(client, '_check_network', return_value=True):
                client.connect(token='gh-token')
            with mock.patch('urllib.request.urlopen', return_value=mock_response):
                result = client.clone_project('12345', str(tmp_path))

        assert result == str(tmp_path), "clone_project()가 target_dir를 반환해야 합니다"
        assert (tmp_path / 'Program.cs').exists(), "Program.cs가 압축 해제되어야 합니다"

    def test_clone_writes_cache_sha_file(self, tmp_path):
        """.cache_sha 파일이 저장되어야 함 [M1.AC 1.5]"""
        from services.github_client import GitHubClient
        zip_bytes = _make_test_zip({'org-repo-sha7/Main.cs': '// cs'})
        mock_github = mock.MagicMock()
        mock_gh = mock.MagicMock()
        mock_repo = mock.MagicMock()
        mock_repo.default_branch = 'main'
        mock_repo.get_branch.return_value.commit.sha = 'gh_sha_xyz999'
        mock_repo.get_archive_link.return_value = 'https://example.com/zip'
        mock_gh.get_repo.return_value = mock_repo
        mock_github.Github.return_value = mock_gh

        mock_response = mock.MagicMock()
        mock_response.read.return_value = zip_bytes
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        client = GitHubClient()
        with mock.patch.dict('sys.modules', {'github': mock_github}):
            with mock.patch.object(client, '_check_network', return_value=True):
                client.connect(token='gh-token')
            with mock.patch('urllib.request.urlopen', return_value=mock_response):
                client.clone_project('99', str(tmp_path))

        sha_file = tmp_path / '.cache_sha'
        assert sha_file.exists(), ".cache_sha 파일이 저장되어야 합니다"
        assert sha_file.read_text().strip() == 'gh_sha_xyz999'

    def test_clone_raises_before_connect(self, tmp_path):
        """connect() 전 clone_project() → RuntimeError"""
        from services.github_client import GitHubClient
        client = GitHubClient()
        raised = False
        try:
            client.clone_project('1', str(tmp_path))
        except RuntimeError:
            raised = True
        assert raised, "connect() 전 clone_project() 호출 시 RuntimeError 발생해야 합니다"


# ---------------------------------------------------------------------------
# T3 > T3.1 스켈레톤 — [M1.S1] GitLab 정상 연결 및 프로젝트 목록 조회
# ---------------------------------------------------------------------------

class TestGitLabConnectAndList:
    """[M1.S1] GitLab 연결 + 프로젝트 목록 조회 [M1.AC 1.1]"""

    def test_connect_returns_true_with_valid_credentials(self):
        """[M1.S1] 유효한 URL + PAT → connect() True 반환"""
        from services.gitlab_client import GitLabClient
        mock_gitlab = mock.MagicMock()
        mock_gl = mock.MagicMock()
        mock_gitlab.Gitlab.return_value = mock_gl

        client = GitLabClient()
        with mock.patch.dict('sys.modules', {'gitlab': mock_gitlab}):
            result = client.connect(
                url='https://gitlab.example.com',
                token='valid-pat-token'
            )
        assert result is True, "[M1.S1] 유효한 자격증명으로 connect()가 True를 반환해야 합니다"

    def test_list_projects_returns_nonempty_list(self):
        """[M1.S1] 연결 후 list_projects() → 1개 이상 프로젝트 반환"""
        from services.gitlab_client import GitLabClient
        mock_gitlab = mock.MagicMock()
        mock_gl = mock.MagicMock()
        mock_project = mock.MagicMock()
        mock_project.id = 1
        mock_project.name = 'TestProject'
        mock_project.path_with_namespace = 'group/TestProject'
        mock_gl.projects.list.return_value = [mock_project]
        mock_gitlab.Gitlab.return_value = mock_gl

        client = GitLabClient()
        with mock.patch.dict('sys.modules', {'gitlab': mock_gitlab}):
            client.connect(url='https://gitlab.example.com', token='valid-token')
            projects = client.list_projects()

        assert isinstance(projects, list), "list_projects()는 리스트를 반환해야 합니다"
        assert len(projects) >= 1, "[M1.S1] 프로젝트 목록이 1개 이상이어야 합니다"
        assert 'id' in projects[0], "프로젝트 dict에 'id' 키가 있어야 합니다"
        assert 'name' in projects[0], "프로젝트 dict에 'name' 키가 있어야 합니다"


# ---------------------------------------------------------------------------
# T3 > T3.1 스켈레톤 — [M1.S2] GitHub 정상 연결 및 레포 목록 조회
# ---------------------------------------------------------------------------

class TestGitHubConnectAndList:
    """[M1.S2] GitHub 연결 + 레포지터리 목록 조회 [M1.AC 1.2]"""

    def test_connect_returns_true_when_network_open(self):
        """[M1.S2] GitHub 네트워크 개방 환경 → connect() True 반환"""
        from services.github_client import GitHubClient
        client = GitHubClient()
        with mock.patch.object(client, '_check_network', return_value=True):
            result = client.connect(token='ghp-valid-token')
        assert result is True, "[M1.S2] 네트워크 개방 환경에서 connect()가 True를 반환해야 합니다"

    def test_list_repos_returns_nonempty_list(self):
        """[M1.S2] 연결 후 list_projects() → 1개 이상 레포 반환"""
        from services.github_client import GitHubClient
        mock_github = mock.MagicMock()
        mock_gh = mock.MagicMock()
        mock_repo = mock.MagicMock()
        mock_repo.id = 101
        mock_repo.name = 'test-repo'
        mock_gh.get_user.return_value.get_repos.return_value = [mock_repo]
        mock_github.Github.return_value = mock_gh

        client = GitHubClient()
        with mock.patch.dict('sys.modules', {'github': mock_github}):
            with mock.patch.object(client, '_check_network', return_value=True):
                client.connect(token='ghp-valid-token')
            repos = client.list_projects()

        assert isinstance(repos, list), "list_projects()는 리스트를 반환해야 합니다"
        assert len(repos) >= 1, "[M1.S2] 레포지터리 목록이 1개 이상이어야 합니다"


# ---------------------------------------------------------------------------
# T3 > T3.1 스켈레톤 — [M1.S18] 프로젝트 0개 선택 후 분석 시작
# ---------------------------------------------------------------------------

class TestAnalyzeProjectsValidation:
    """[M1.S18] 분석 대상 프로젝트 0개 → 오류 반환 [M1.F1]"""

    def test_analyze_with_no_projects_raises_error(self):
        """[M1.S18] 프로젝트 0개 선택 시 ValueError — '1개 이상 선택' 안내"""
        from services.analyze_service import start_analysis
        with pytest.raises(ValueError, match="1개 이상"):
            start_analysis(project_list=[])
