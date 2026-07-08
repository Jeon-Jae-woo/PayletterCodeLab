"""
T1 > T1.5 Composition Root 및 GitLab Mock 어댑터 검증 테스트

[PR-3] EnvironmentDivergence, [GR-1.6] Port-Adapter 계약 준수 검증.
GitLabMockClient가 SourceManager 인터페이스를 완전히 충족하는지 검증.
"""
import os
import sys
import importlib

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestSourceManagerInterface:
    """SourceManager 포트 인터페이스 정의 검증 [Normal 시나리오]"""

    def test_source_manager_is_importable(self):
        """SourceManager가 services.source_service에서 임포트 가능해야 함"""
        from services.source_service import SourceManager
        assert SourceManager is not None

    def test_source_manager_has_connect_method(self):
        """connect() 추상 메서드 시그니처 존재"""
        from services.source_service import SourceManager
        assert hasattr(SourceManager, 'connect'), "SourceManager에 connect() 없음"

    def test_source_manager_has_list_projects_method(self):
        """list_projects() 추상 메서드 시그니처 존재"""
        from services.source_service import SourceManager
        assert hasattr(SourceManager, 'list_projects'), "SourceManager에 list_projects() 없음"

    def test_source_manager_has_clone_project_method(self):
        """clone_project() 추상 메서드 시그니처 존재"""
        from services.source_service import SourceManager
        assert hasattr(SourceManager, 'clone_project'), "SourceManager에 clone_project() 없음"

    def test_source_manager_is_abstract(self):
        """SourceManager는 직접 인스턴스화 불가 (추상 클래스)"""
        from services.source_service import SourceManager
        try:
            SourceManager()
            raise AssertionError("추상 클래스 SourceManager가 인스턴스화되어서는 안 됩니다")
        except TypeError:
            pass  # 예상된 동작 — 추상 메서드 미구현으로 TypeError


class TestGitLabMockClientContract:
    """GitLabMockClient SourceManager 인터페이스 계약 검증 [Normal 시나리오]"""

    def setup_method(self):
        from services.gitlab_mock import GitLabMockClient
        self._client = GitLabMockClient()

    def test_mock_client_implements_source_manager(self):
        """GitLabMockClient가 SourceManager 인스턴스여야 함"""
        from services.source_service import SourceManager
        assert isinstance(self._client, SourceManager), \
            "GitLabMockClient가 SourceManager를 구현하지 않습니다"

    def test_mock_connect_returns_true(self):
        """Mock의 connect()는 항상 True 반환 (네트워크 없이 연결 성공 모사)"""
        result = self._client.connect()
        assert result is True, "GitLabMockClient.connect()가 True를 반환해야 합니다"

    def test_mock_list_projects_returns_list(self):
        """list_projects()가 리스트를 반환해야 함"""
        projects = self._client.list_projects()
        assert isinstance(projects, list), "list_projects()가 리스트를 반환하지 않습니다"

    def test_mock_list_projects_not_empty(self):
        """Mock 프로젝트 목록이 비어 있지 않아야 함 (샘플 데이터)"""
        projects = self._client.list_projects()
        assert len(projects) > 0, "GitLabMockClient 샘플 프로젝트가 없습니다"

    def test_mock_project_has_required_fields(self):
        """각 프로젝트 항목에 id, name, path 필드가 있어야 함"""
        projects = self._client.list_projects()
        for project in projects:
            assert 'id' in project, f"프로젝트에 'id' 필드 없음: {project}"
            assert 'name' in project, f"프로젝트에 'name' 필드 없음: {project}"
            assert 'path' in project, f"프로젝트에 'path' 필드 없음: {project}"

    def test_mock_clone_project_returns_path(self):
        """clone_project()가 경로 문자열을 반환해야 함"""
        result = self._client.clone_project(project_id='1', target_dir='/tmp/test')
        assert isinstance(result, str), "clone_project()가 문자열 경로를 반환해야 합니다"
        assert len(result) > 0, "clone_project()가 빈 경로를 반환해서는 안 됩니다"

    def test_mock_does_not_make_network_calls(self):
        """Mock 어댑터는 실제 네트워크 호출 없이 동작해야 함"""
        import socket
        original_getaddrinfo = socket.getaddrinfo
        calls = []

        def tracking_getaddrinfo(*args, **kwargs):
            calls.append(args)
            return original_getaddrinfo(*args, **kwargs)

        socket.getaddrinfo = tracking_getaddrinfo
        try:
            self._client.connect()
            self._client.list_projects()
        finally:
            socket.getaddrinfo = original_getaddrinfo

        assert not calls, "Mock 어댑터가 실제 네트워크 호출을 수행했습니다"


class TestCompositionRoot:
    """Composition Root 환경 분기 검증 [Normal/Boundary 시나리오]"""

    def test_gitlab_mock_flag_returns_mock_client(self):
        """GITLAB_MOCK=true 환경 변수 시 MockClient 반환"""
        os.environ['GITLAB_MOCK'] = 'true'
        try:
            # app 모듈을 리로드하여 환경 변수 변경 반영
            from config import get_config
            cfg = get_config()
            assert cfg['GITLAB_MOCK'] is True, "GITLAB_MOCK=true 설정이 반영되지 않았습니다"
        finally:
            del os.environ['GITLAB_MOCK']

    def test_gitlab_mock_false_disables_mock(self):
        """GITLAB_MOCK 미설정 시 Mock 비활성"""
        os.environ.pop('GITLAB_MOCK', None)
        from config import get_config
        cfg = get_config()
        assert cfg['GITLAB_MOCK'] is False, "GITLAB_MOCK 기본값은 False여야 합니다"

    def test_github_disabled_flag(self):
        """GITHUB_DISABLED=true 환경 변수 설정 확인 (폐쇄망 config-externalize)"""
        os.environ['GITHUB_DISABLED'] = 'true'
        try:
            from config import get_config
            cfg = get_config()
            assert cfg['GITHUB_DISABLED'] is True, "GITHUB_DISABLED=true 설정이 반영되지 않았습니다"
        finally:
            del os.environ['GITHUB_DISABLED']


class TestConfigSecurity:
    """config.py 보안 검증 [Security 시나리오] — [GR-1.4]"""

    def test_config_reads_from_env_not_file(self):
        """config.py가 .env 파일을 읽지 않아야 함"""
        import inspect
        import config as cfg_module
        source = inspect.getsource(cfg_module)
        # .env 파일 직접 오픈 패턴 금지 검사
        assert "open('.env')" not in source, "config.py가 .env 파일을 직접 오픈합니다"
        assert "load_dotenv" not in source, "config.py가 dotenv를 로드합니다 ([GR-1.4] 위반)"

    def test_no_hardcoded_tokens_in_config(self):
        """config.py에 하드코딩된 토큰/시크릿이 없어야 함"""
        import inspect
        import config as cfg_module
        source = inspect.getsource(cfg_module)
        # 일반적인 하드코딩 시크릿 패턴 검출
        suspicious = ['ghp_', 'glpat-', 'sk-', 'Bearer ', 'password=']
        found = [p for p in suspicious if p in source]
        assert not found, f"config.py에 하드코딩 시크릿 패턴 발견: {found}"

    def test_gitlab_token_from_env(self):
        """GITLAB_TOKEN은 환경 변수에서 로드해야 함"""
        os.environ['GITLAB_TOKEN'] = 'test-token-value'
        try:
            import config as cfg_module
            importlib.reload(cfg_module)
            cfg = cfg_module.get_config()
            assert cfg['GITLAB_TOKEN'] == 'test-token-value', \
                "GITLAB_TOKEN이 환경 변수에서 로드되지 않습니다"
        finally:
            del os.environ['GITLAB_TOKEN']


class TestGitHubClientNetworkCheck:
    """GitHubClient 폐쇄망 감지 검증 [Normal/Exception 시나리오] — [M1.EX-2]"""

    def setup_method(self):
        from services.github_client import GitHubClient
        self._client = GitHubClient()

    def test_check_network_returns_true_on_success(self):
        """네트워크 연결 성공 시 True 반환"""
        from unittest import mock
        # MagicMock은 컨텍스트 매니저 프로토콜을 자동 지원하므로 별도 설정 불필요
        with mock.patch('socket.create_connection'):
            result = self._client._check_network(timeout=1)
        assert result is True, "_check_network()가 연결 성공 시 True를 반환해야 합니다"

    def test_check_network_returns_false_on_oserror(self):
        """OSError 발생 시 False 반환 (폐쇄망 판정)"""
        from unittest import mock
        with mock.patch('socket.create_connection', side_effect=OSError("연결 실패")):
            result = self._client._check_network(timeout=1)
        assert result is False, "_check_network()가 OSError 시 False를 반환해야 합니다"

    def test_connect_raises_on_network_block(self):
        """폐쇄망 감지 시 ConnectionError 발생 [M1.EX-2]"""
        from unittest import mock
        with mock.patch.object(self._client, '_check_network', return_value=False):
            try:
                self._client.connect(token='')
                raise AssertionError("ConnectionError가 발생해야 합니다")
            except ConnectionError as e:
                assert '[M1.EX-2]' in str(e), "오류 메시지에 [M1.EX-2] 포함 필수"

    def test_list_projects_raises_without_connect(self):
        """connect() 없이 list_projects() 호출 시 RuntimeError"""
        try:
            self._client.list_projects()
            raise AssertionError("RuntimeError가 발생해야 합니다")
        except RuntimeError:
            pass

    def test_clone_project_raises_without_connect(self):
        """connect() 없이 clone_project() 호출 시 RuntimeError"""
        try:
            self._client.clone_project('1', '/tmp/test')
            raise AssertionError("RuntimeError가 발생해야 합니다")
        except RuntimeError:
            pass

    def test_client_implements_source_manager(self):
        """GitHubClient가 SourceManager 인터페이스를 구현해야 함"""
        from services.source_service import SourceManager
        assert isinstance(self._client, SourceManager), \
            "GitHubClient가 SourceManager를 구현하지 않습니다"

    def test_connect_succeeds_when_network_open(self):
        """네트워크 허용 시 connect()가 True 반환 [QA-SC-001 보완]"""
        from unittest import mock
        mock_github_module = mock.MagicMock()
        mock_gh_instance = mock.MagicMock()
        mock_github_module.Github.return_value = mock_gh_instance
        with mock.patch.dict('sys.modules', {'github': mock_github_module}):
            with mock.patch.object(self._client, '_check_network', return_value=True):
                result = self._client.connect(token='test-token')
        assert result is True, "connect()가 네트워크 허용 시 True를 반환해야 합니다"
        mock_github_module.Github.assert_called_once_with('test-token')

    def test_list_projects_after_connect(self):
        """connect() 후 list_projects()가 저장소 목록을 반환해야 함 [QA-SC-001 보완]"""
        from unittest import mock
        mock_github_module = mock.MagicMock()
        mock_repo = mock.MagicMock()
        mock_repo.id = 42
        mock_repo.name = 'TestRepo'
        mock_repo.full_name = 'user/TestRepo'
        mock_github_module.Github.return_value.get_user.return_value.get_repos.return_value = [mock_repo]
        with mock.patch.dict('sys.modules', {'github': mock_github_module}):
            with mock.patch.object(self._client, '_check_network', return_value=True):
                self._client.connect(token='test-token')
                projects = self._client.list_projects()
        assert isinstance(projects, list), "list_projects()가 리스트를 반환해야 합니다"
        assert len(projects) == 1
        assert projects[0] == {'id': '42', 'name': 'TestRepo', 'path': 'user/TestRepo'}

    def test_clone_project_after_connect(self, tmp_path):
        """connect() 후 clone_project()가 target_dir를 반환해야 함 [QA-SC-001 보완]"""
        import io
        import zipfile
        from unittest import mock
        # 테스트용 ZIP 생성 (최상위 디렉터리 포함)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('repo-main-abc/', '')
            zf.writestr('repo-main-abc/Main.cs', '// cs')
        zip_bytes = buf.getvalue()

        mock_github_module = mock.MagicMock()
        mock_repo = mock.MagicMock()
        mock_repo.default_branch = 'main'
        mock_repo.get_branch.return_value.commit.sha = 'gh_sha_abc'
        mock_repo.get_archive_link.return_value = 'https://example.com/archive.zip'
        mock_github_module.Github.return_value.get_repo.return_value = mock_repo

        mock_response = mock.MagicMock()
        mock_response.read.return_value = zip_bytes
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        target = str(tmp_path)
        with mock.patch.dict('sys.modules', {'github': mock_github_module}):
            with mock.patch.object(self._client, '_check_network', return_value=True):
                self._client.connect(token='test-token')
            with mock.patch('urllib.request.urlopen', return_value=mock_response):
                result = self._client.clone_project('42', target)
        assert result == target, "clone_project()가 target_dir를 반환해야 합니다"


class TestGitLabClientContract:
    """GitLabClient SourceManager 인터페이스 계약 검증 [Normal/Exception 시나리오]"""

    def setup_method(self):
        from services.gitlab_client import GitLabClient
        self._client = GitLabClient()

    def test_client_implements_source_manager(self):
        """GitLabClient가 SourceManager 인터페이스를 구현해야 함"""
        from services.source_service import SourceManager
        assert isinstance(self._client, SourceManager), \
            "GitLabClient가 SourceManager를 구현하지 않습니다"

    def test_list_projects_raises_without_connect(self):
        """connect() 없이 list_projects() 호출 시 RuntimeError"""
        try:
            self._client.list_projects()
            raise AssertionError("RuntimeError가 발생해야 합니다")
        except RuntimeError:
            pass

    def test_clone_project_raises_without_connect(self):
        """connect() 없이 clone_project() 호출 시 RuntimeError"""
        try:
            self._client.clone_project('1', '/tmp/test')
            raise AssertionError("RuntimeError가 발생해야 합니다")
        except RuntimeError:
            pass

    def test_connect_uses_python_gitlab(self):
        """connect()가 python-gitlab 라이브러리를 사용해야 함"""
        from unittest import mock
        mock_gitlab_module = mock.MagicMock()
        mock_instance = mock.MagicMock()
        mock_gitlab_module.Gitlab.return_value = mock_instance
        with mock.patch.dict('sys.modules', {'gitlab': mock_gitlab_module}):
            result = self._client.connect(url='https://gitlab.example.com', token='test')
        assert result is True, "connect()가 True를 반환해야 합니다"
        mock_instance.auth.assert_called_once()

    def test_list_projects_after_connect(self):
        """connect() 후 list_projects()가 프로젝트 목록을 반환해야 함"""
        from unittest import mock
        mock_gitlab_module = mock.MagicMock()
        mock_project = mock.MagicMock()
        mock_project.id = 1
        mock_project.name = 'TestProject'
        mock_project.path_with_namespace = 'group/test'
        mock_gitlab_module.Gitlab.return_value.projects.list.return_value = [mock_project]
        with mock.patch.dict('sys.modules', {'gitlab': mock_gitlab_module}):
            self._client.connect(url='https://gitlab.example.com', token='test')
            projects = self._client.list_projects()
        assert isinstance(projects, list), "list_projects()가 리스트를 반환해야 합니다"
        assert len(projects) == 1
        assert projects[0]['id'] == '1'
        assert projects[0]['name'] == 'TestProject'

    def test_clone_project_after_connect(self, tmp_path):
        """connect() 후 clone_project()가 경로를 반환해야 함"""
        import io
        import zipfile
        from unittest import mock
        # 테스트용 ZIP 생성 (최상위 디렉터리 포함)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('project-main-sha/', '')
            zf.writestr('project-main-sha/App.cs', '// cs')
        zip_bytes = buf.getvalue()

        mock_gitlab_module = mock.MagicMock()
        mock_project = mock.MagicMock()
        mock_commit = mock.MagicMock()
        mock_commit.id = 'gl_sha_xyz'
        mock_project.repository_archive.return_value = zip_bytes
        mock_project.commits.list.return_value = [mock_commit]
        mock_gitlab_module.Gitlab.return_value.projects.get.return_value = mock_project

        target = str(tmp_path)
        with mock.patch.dict('sys.modules', {'gitlab': mock_gitlab_module}):
            self._client.connect(url='https://gitlab.example.com', token='test')
            result = self._client.clone_project('1', target)
        assert result == target, "clone_project()가 target_dir를 반환해야 합니다"


class TestCompositionRootAdapter:
    """get_gitlab_adapter() Composition Root 분기 검증 [Normal 시나리오]"""

    def test_mock_flag_returns_mock_client(self):
        """GITLAB_MOCK=true 시 GitLabMockClient 반환"""
        os.environ['GITLAB_MOCK'] = 'true'
        try:
            import app as app_module
            importlib.reload(app_module)
            adapter = app_module.get_gitlab_adapter()
            from services.gitlab_mock import GitLabMockClient
            assert isinstance(adapter, GitLabMockClient), \
                "GITLAB_MOCK=true 시 GitLabMockClient를 반환해야 합니다"
        finally:
            del os.environ['GITLAB_MOCK']

    def test_no_mock_flag_returns_real_client(self):
        """GITLAB_MOCK 미설정 시 GitLabClient 반환"""
        os.environ.pop('GITLAB_MOCK', None)
        import app as app_module
        importlib.reload(app_module)
        adapter = app_module.get_gitlab_adapter()
        from services.gitlab_client import GitLabClient
        assert isinstance(adapter, GitLabClient), \
            "GITLAB_MOCK 미설정 시 GitLabClient를 반환해야 합니다"
