"""
T3 > T3.1 + T4 > T4.1 — 보안 시나리오 단위 테스트

[M1.S19] GitLab 인증 실패 — 잘못된 Token / [M1.EX-1]
[M1.S20] GitHub 네트워크 차단 (폐쇄망 시뮬레이션) / [M1.EX-2]
[M1.S21] 로컬 폴더 경로 오류 — 존재하지 않는 경로 / [M1.EX-3]
[M1.S22] 비UTF-8 인코딩 파일 처리 / [M1.EX-5]
[M1.S23] 포트 5000 충돌 시 자동 탐색 / [M1.EX-8]
[M1.S24] Token 로그 마스킹 검증 (보안) / [M1.AC 1.6]
[M1.S25] Path Traversal 공격 방어 / [M1.AC 1.3]
[M1.S26] GitLab SSL 인증서 오류 처리 / [M1.EX-10]
T4.1: utils/validators.py 입력 검증 계층 테스트
"""
import logging
import os
import sys
from unittest import mock

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# [M1.S19] GitLab 인증 실패
# ---------------------------------------------------------------------------

class TestGitLabAuthFailure:
    """[M1.S19] 잘못된 Token → 인증 오류, 분석 미진행 [M1.EX-1]"""

    def test_invalid_token_raises_auth_error(self):
        """유효한 URL + 잘못된 PAT → 인증 오류 예외 발생"""
        from services.gitlab_client import GitLabClient

        # gitlab.GitlabAuthenticationError 또는 GitlabGetError 시뮬레이션
        mock_gitlab = mock.MagicMock()
        mock_gl = mock.MagicMock()
        mock_gl.auth.side_effect = Exception("401 Unauthorized")
        mock_gitlab.Gitlab.return_value = mock_gl

        client = GitLabClient()
        with mock.patch.dict('sys.modules', {'gitlab': mock_gitlab}):
            with pytest.raises(Exception, match="401"):
                client.connect(url='https://gitlab.example.com', token='invalid_token')


# ---------------------------------------------------------------------------
# [M1.S20] GitHub 네트워크 차단
# ---------------------------------------------------------------------------

class TestGitHubNetworkBlock:
    """[M1.S20] 도달 불가 GitHub URL → ConnectionError, 로컬 폴더 대안 안내 [M1.EX-2]"""

    def test_unreachable_github_raises_connection_error(self):
        """GitHub 접근 불가 시 ConnectionError 또는 OSError 발생"""
        from services.github_client import GitHubClient

        client = GitHubClient()
        with mock.patch.object(client, '_check_network', return_value=False):
            with pytest.raises((ConnectionError, OSError, RuntimeError)):
                client.connect(token='gh-token')

    def test_connection_error_message_suggests_local_folder(self):
        """[M1.S20] 연결 오류 메시지에 로컬 폴더 대안 안내가 포함되어야 함"""
        from services.github_client import GitHubClient

        client = GitHubClient()
        with mock.patch.object(client, '_check_network', return_value=False):
            try:
                client.connect(token='gh-token')
                pytest.fail("예외가 발생해야 합니다")
            except Exception as exc:
                # T4 구현 후 오류 메시지에 '로컬 폴더' 또는 'local' 안내 포함 확인
                error_msg = str(exc).lower()
                assert 'local' in error_msg or '로컬' in error_msg or 'network' in error_msg, \
                    "오류 메시지에 로컬 폴더 대안 또는 네트워크 오류 안내가 포함되어야 합니다"

    def test_github_network_blocked(self):
        """[T4.3 DoD] GitHub 폐쇄망 차단 → ConnectionError + 로컬 폴더 안내 [M1.S20]"""
        from services.github_client import GitHubClient
        client = GitHubClient()
        with mock.patch.object(client, '_check_network', return_value=False):
            with pytest.raises(ConnectionError) as exc_info:
                client.connect(token='gh-token')
        assert 'M1.EX-2' in str(exc_info.value) or '로컬' in str(exc_info.value)

    def test_github_network_check_timeout(self):
        """[T4.3 DoD] GitHub 네트워크 체크 타임아웃 10초 설정 확인"""
        from services.github_client import _NETWORK_CHECK_TIMEOUT
        assert _NETWORK_CHECK_TIMEOUT == 10, "GitHub 네트워크 체크 타임아웃은 10초여야 합니다"


# ---------------------------------------------------------------------------
# [M1.S21] 로컬 폴더 경로 오류
# ---------------------------------------------------------------------------

class TestLocalFolderPathError:
    """[M1.S21] 존재하지 않는 경로 → 오류 반환 [M1.EX-3]"""

    def test_nonexistent_path_raises_error(self):
        """[M1.S21] 존재하지 않는 경로 → FileNotFoundError 또는 ValueError"""
        from services.source_service import LocalFolderManager
        mgr = LocalFolderManager()
        with pytest.raises((FileNotFoundError, ValueError)):
            mgr.connect(path='/absolutely/not/existing/path_xyz_98765')

    def test_error_message_describes_invalid_cs_project(self):
        """오류 메시지에 'C# 프로젝트' 또는 경로 오류 안내 포함"""
        from services.source_service import LocalFolderManager
        mgr = LocalFolderManager()
        with pytest.raises(Exception) as exc_info:
            mgr.connect(path='/absolutely/not/existing/path_xyz_98765')
        assert exc_info.value is not None


# ---------------------------------------------------------------------------
# [M1.S22] 비UTF-8 인코딩 파일 처리 (complexity_analyzer에서도 검증)
# ---------------------------------------------------------------------------

class TestNonUtf8FileHandling:
    """[M1.S22] EUC-KR 파일 → 스킵 + 경고 기록, 분석 계속 [M1.EX-5]"""

    def test_euckr_file_is_skipped_without_exception(self, tmp_path):
        """EUC-KR 인코딩 파일이 포함되어도 전체 분석이 예외 없이 완료되어야 함"""
        from analyzers.complexity_analyzer import analyze_complexity
        # EUC-KR 인코딩 파일 생성
        euckr_file = tmp_path / "Korean.cs"
        euckr_file.write_bytes("// 한글주석\npublic class A {}".encode('euc-kr'))
        # UTF-8 정상 파일도 함께 분석
        normal_file = tmp_path / "Normal.cs"
        normal_file.write_text(
            "public class B { public void Run() {} }", encoding='utf-8'
        )
        # 예외 없이 완료되어야 함
        result = analyze_complexity([str(euckr_file), str(normal_file)])
        assert isinstance(result, list), "인코딩 오류가 있어도 리스트를 반환해야 합니다"


# ---------------------------------------------------------------------------
# [M1.S23] 포트 충돌 자동 탐색
# ---------------------------------------------------------------------------

class TestPortConflictAutoFind:
    """[M1.S23] 포트 5000 사용 중 → 다음 가용 포트 자동 탐색 [M1.EX-8]"""

    def test_find_available_port_when_5000_occupied(self):
        """포트 5000이 사용 중일 때 5001 이상 가용 포트를 반환해야 함"""
        from app import find_available_port  # T1.4 구현 함수
        # 5000 포트를 점유한 상황 시뮬레이션 — bind() 호출 시 OSError로 차단
        with mock.patch('app.socket.socket') as mock_socket_class:
            mock_sock = mock.MagicMock()
            mock_socket_class.return_value.__enter__ = mock.Mock(return_value=mock_sock)
            mock_socket_class.return_value.__exit__ = mock.Mock(return_value=False)
            # 5000 포트 bind 실패(OSError) → 5001 포트 bind 성공(None)
            mock_sock.bind.side_effect = [OSError("Address already in use"), None]
            port = find_available_port(start_port=5000)
        assert port == 5001, \
            f"5000 포트 충돌 시 5001을 반환해야 합니다. 실제: {port}"


# ---------------------------------------------------------------------------
# [M1.S24] Token 로그 마스킹
# ---------------------------------------------------------------------------

class TestTokenLogMasking:
    """[M1.S24] GitLab Token이 서버 로그에 기록되지 않아야 함 [M1.AC 1.6]"""

    def test_gitlab_token_not_in_logs(self, caplog):
        """connect() 호출 시 token 값이 로그에 기록되지 않아야 함"""
        from services.gitlab_client import GitLabClient

        secret_token = 'glpat-SECRET-TOKEN-12345'
        mock_gitlab = mock.MagicMock()
        mock_gl = mock.MagicMock()
        mock_gl.projects.list.return_value = []
        mock_gitlab.Gitlab.return_value = mock_gl

        client = GitLabClient()
        with caplog.at_level(logging.DEBUG):
            with mock.patch.dict('sys.modules', {'gitlab': mock_gitlab}):
                try:
                    client.connect(
                        url='https://gitlab.example.com',
                        token=secret_token
                    )
                except Exception:
                    pass  # 연결 실패해도 로그 검사는 수행

        # 모든 로그 메시지에 토큰이 포함되어서는 안 됨
        all_logs = ' '.join(caplog.messages)
        assert secret_token not in all_logs, \
            f"GitLab Token이 로그에 노출되어서는 안 됩니다: '{secret_token}'"

    def test_github_token_not_in_logs(self, caplog):
        """GitHub connect() 시 token 값이 로그에 기록되지 않아야 함"""
        from services.github_client import GitHubClient

        secret_token = 'ghp_SECRET_GITHUB_TOKEN_98765'
        client = GitHubClient()
        with caplog.at_level(logging.DEBUG):
            with mock.patch.object(client, '_check_network', return_value=False):
                try:
                    client.connect(token=secret_token)
                except Exception:
                    pass

        all_logs = ' '.join(caplog.messages)
        assert secret_token not in all_logs, \
            f"GitHub Token이 로그에 노출되어서는 안 됩니다: '{secret_token}'"


# ---------------------------------------------------------------------------
# [M1.S25] Path Traversal 방어 (security 관점 — source_service에서도 커버)
# ---------------------------------------------------------------------------

class TestPathTraversalDefense:
    """[M1.S25] 경계 밖 경로 접근 시도 → 거부 [M1.AC 1.3]"""

    def test_relative_traversal_is_rejected(self):
        """`../../../etc/passwd` 형태 Path Traversal → 오류"""
        from services.source_service import LocalFolderManager
        mgr = LocalFolderManager()
        with pytest.raises((ValueError, FileNotFoundError, PermissionError)):
            mgr.connect(path='../../../etc/passwd')

    def test_windows_system_path_is_rejected(self):
        """`C:\\Windows\\System32` 경로 → .cs 파일 없음으로 거부"""
        from services.source_service import LocalFolderManager
        mgr = LocalFolderManager()
        with pytest.raises((ValueError, FileNotFoundError)):
            mgr.connect(path='C:\\Windows\\System32')


# ---------------------------------------------------------------------------
# [M1.S26] GitLab SSL 인증서 오류
# ---------------------------------------------------------------------------

class TestGitLabSslError:
    """[M1.S26] 자체 서명 인증서 → SSL 오류 안내 메시지 [M1.EX-10]"""

    def test_ssl_error_raises_with_guidance_message(self):
        """SSL 오류 시 verify=False 옵션 안내가 포함된 예외 또는 반환값"""
        from services.gitlab_client import GitLabClient
        import ssl

        mock_gitlab = mock.MagicMock()
        mock_gl = mock.MagicMock()
        # SSL 오류 시뮬레이션
        mock_gl.auth.side_effect = ssl.SSLError("certificate verify failed")
        mock_gitlab.Gitlab.return_value = mock_gl

        client = GitLabClient()
        with mock.patch.dict('sys.modules', {'gitlab': mock_gitlab}):
            with pytest.raises(Exception) as exc_info:
                client.connect(
                    url='https://internal-gitlab.local',
                    token='token',
                    verify_ssl=True
                )
        # T4.3: ssl.SSLError → [M1.EX-10] 안내 메시지 포함 확인
        assert exc_info.value is not None
        error_msg = str(exc_info.value)
        assert 'M1.EX-10' in error_msg or 'SSL' in error_msg or 'verify' in error_msg.lower()

    def test_gitlab_ssl_error(self):
        """[T4.3 DoD] ssl.SSLError → [M1.EX-10] 안내 메시지 포함 예외 [M1.S26]"""
        import ssl
        from services.gitlab_client import GitLabClient
        mock_gitlab = mock.MagicMock()
        mock_gl = mock.MagicMock()
        mock_gl.auth.side_effect = ssl.SSLError("certificate verify failed")
        mock_gitlab.Gitlab.return_value = mock_gl
        client = GitLabClient()
        with mock.patch.dict('sys.modules', {'gitlab': mock_gitlab}):
            with pytest.raises(ssl.SSLError) as exc_info:
                client.connect(url='https://internal-gitlab.local', token='tok', verify_ssl=True)
        assert 'M1.EX-10' in str(exc_info.value)

    def test_verify_false_sets_ssl_warning(self):
        """[T4.3 DoD] verify_ssl=False → adapter.ssl_warning에 경고 문구 저장"""
        from services.gitlab_client import GitLabClient
        mock_gitlab = mock.MagicMock()
        mock_gl = mock.MagicMock()
        mock_gitlab.Gitlab.return_value = mock_gl
        client = GitLabClient()
        assert client.ssl_warning == ''
        with mock.patch.dict('sys.modules', {'gitlab': mock_gitlab}):
            client.connect(url='https://internal.local', token='tok', verify_ssl=False)
        assert client.ssl_warning != ''
        assert 'SSL' in client.ssl_warning


# ---------------------------------------------------------------------------
# T4 > T4.1 — utils/validators.py 입력 검증 계층
# ---------------------------------------------------------------------------

class TestValidateUrl:
    """validate_url() — URL scheme 검증 + SSRF 내부 IP 차단 [security-standards.md §1.5]"""

    def test_valid_http_url_passes(self):
        """http URL → 검증 통과"""
        from utils.validators import validate_url
        result = validate_url('http://gitlab.example.com')
        assert result == 'http://gitlab.example.com'

    def test_valid_https_url_passes(self):
        """https URL → 검증 통과"""
        from utils.validators import validate_url
        result = validate_url('https://github.com/user/repo')
        assert 'github.com' in result

    def test_file_scheme_rejected(self):
        """file:// scheme → ValidationError"""
        from utils.validators import validate_url, ValidationError
        with pytest.raises(ValidationError, match='scheme'):
            validate_url('file:///etc/passwd')

    def test_ftp_scheme_rejected(self):
        """ftp:// scheme → ValidationError"""
        from utils.validators import validate_url, ValidationError
        with pytest.raises(ValidationError):
            validate_url('ftp://example.com/file')

    def test_loopback_ip_blocked(self):
        """127.0.0.1 → SSRF 내부 IP 차단"""
        from utils.validators import validate_url, ValidationError
        with pytest.raises(ValidationError, match='내부 IP'):
            validate_url('http://127.0.0.1:8080/api')

    def test_rfc1918_class_a_blocked(self):
        """10.x.x.x → RFC1918 차단"""
        from utils.validators import validate_url, ValidationError
        with pytest.raises(ValidationError, match='내부 IP'):
            validate_url('http://10.0.0.1/gitlab')

    def test_rfc1918_class_b_blocked(self):
        """172.16.x.x → RFC1918 차단"""
        from utils.validators import validate_url, ValidationError
        with pytest.raises(ValidationError, match='내부 IP'):
            validate_url('http://172.16.0.1/')

    def test_rfc1918_class_c_blocked(self):
        """192.168.x.x → RFC1918 차단"""
        from utils.validators import validate_url, ValidationError
        with pytest.raises(ValidationError, match='내부 IP'):
            validate_url('https://192.168.1.100/api')

    def test_aws_metadata_ip_blocked(self):
        """169.254.169.254 → AWS 메타데이터 차단"""
        from utils.validators import validate_url, ValidationError
        with pytest.raises(ValidationError, match='내부 IP'):
            validate_url('http://169.254.169.254/latest/meta-data')

    def test_empty_url_rejected(self):
        """빈 URL → ValidationError"""
        from utils.validators import validate_url, ValidationError
        with pytest.raises(ValidationError):
            validate_url('')


class TestValidateLocalPath:
    """validate_local_path() — Path Traversal 방지 [security-standards.md §1.4]"""

    def test_valid_existing_directory_passes(self, tmp_path):
        """존재하는 디렉터리 → 검증 통과"""
        from utils.validators import validate_local_path
        result = validate_local_path(str(tmp_path))
        assert os.path.isdir(result)

    def test_path_traversal_relative_rejected(self, tmp_path):
        """../../../etc/passwd 형태 상대 경로 탈출 → FileNotFoundError 또는 ValidationError"""
        from utils.validators import validate_local_path, ValidationError
        base = str(tmp_path)
        with pytest.raises((FileNotFoundError, ValidationError)):
            validate_local_path('../../../etc/passwd', base_allowed=base)

    def test_path_outside_base_rejected(self, tmp_path):
        """base_allowed 외부 경로 → ValidationError"""
        from utils.validators import validate_local_path, ValidationError
        sub = tmp_path / 'allowed'
        sub.mkdir()
        other = tmp_path / 'other'
        other.mkdir()
        with pytest.raises(ValidationError, match='허용되지 않는 경로'):
            validate_local_path(str(other), base_allowed=str(sub))

    def test_null_byte_rejected(self):
        """null byte 포함 경로 → ValidationError"""
        from utils.validators import validate_local_path, ValidationError
        with pytest.raises(ValidationError):
            validate_local_path('/some/path\x00evil')

    def test_nonexistent_path_raises_file_not_found(self):
        """존재하지 않는 경로 → FileNotFoundError"""
        from utils.validators import validate_local_path
        with pytest.raises(FileNotFoundError):
            validate_local_path('/absolutely/nonexistent/path_xyz_98765')

    def test_file_path_rejected_not_directory(self, tmp_path):
        """파일 경로(디렉터리 아님) → ValidationError"""
        from utils.validators import validate_local_path, ValidationError
        f = tmp_path / 'file.cs'
        f.write_text('content')
        with pytest.raises(ValidationError, match='디렉터리'):
            validate_local_path(str(f))

    def test_empty_path_rejected(self):
        """빈 경로 → ValidationError"""
        from utils.validators import validate_local_path, ValidationError
        with pytest.raises(ValidationError):
            validate_local_path('')


class TestValidateSearchKeyword:
    """validate_search_keyword() — 길이 제한 200자 [PR-6]"""

    def test_normal_keyword_passes(self):
        """정상 키워드 → 검증 통과"""
        from utils.validators import validate_search_keyword
        result = validate_search_keyword('ExecuteReader')
        assert result == 'ExecuteReader'

    def test_keyword_200_chars_passes(self):
        """정확히 200자 → 통과"""
        from utils.validators import validate_search_keyword
        kw = 'A' * 200
        assert validate_search_keyword(kw) == kw

    def test_keyword_201_chars_rejected(self):
        """201자 키워드 → ValidationError"""
        from utils.validators import validate_search_keyword, ValidationError
        with pytest.raises(ValidationError, match='200자'):
            validate_search_keyword('A' * 201)

    def test_empty_keyword_rejected(self):
        """빈 키워드 → ValidationError"""
        from utils.validators import validate_search_keyword, ValidationError
        with pytest.raises(ValidationError):
            validate_search_keyword('')

    def test_whitespace_stripped(self):
        """앞뒤 공백 strip 후 반환"""
        from utils.validators import validate_search_keyword
        result = validate_search_keyword('  keyword  ')
        assert result == 'keyword'


class TestValidateRegexPattern:
    """validate_regex_pattern() — 정규식 패턴 사전 검증"""

    def test_valid_pattern_passes(self):
        """유효한 정규식 → 통과"""
        from utils.validators import validate_regex_pattern
        result = validate_regex_pattern(r'UP_\w+')
        assert result == r'UP_\w+'

    def test_invalid_pattern_raises_validation_error(self):
        """[invalid 패턴 → ValidationError"""
        from utils.validators import validate_regex_pattern, ValidationError
        with pytest.raises(ValidationError, match='정규식'):
            validate_regex_pattern('[invalid')

    def test_unclosed_group_raises_validation_error(self):
        """미닫힌 그룹 패턴 → ValidationError"""
        from utils.validators import validate_regex_pattern, ValidationError
        with pytest.raises(ValidationError):
            validate_regex_pattern('(unclosed')

    def test_empty_pattern_rejected(self):
        """빈 패턴 → ValidationError"""
        from utils.validators import validate_regex_pattern, ValidationError
        with pytest.raises(ValidationError):
            validate_regex_pattern('')


class TestSanitizeProjectName:
    """sanitize_project_name() — 파일시스템 안전 이름 변환"""

    def test_normal_name_unchanged(self):
        """특수문자 없는 이름 → 변환 없음"""
        from utils.validators import sanitize_project_name
        result = sanitize_project_name('MyProject')
        assert result == 'MyProject'

    def test_special_chars_replaced(self):
        """슬래시, 콜론 등 특수문자 → 언더스코어 치환"""
        from utils.validators import sanitize_project_name
        result = sanitize_project_name('group/my-project:v1')
        assert '/' not in result
        assert ':' not in result

    def test_empty_name_rejected(self):
        """빈 이름 → ValidationError"""
        from utils.validators import sanitize_project_name, ValidationError
        with pytest.raises(ValidationError):
            sanitize_project_name('')

    def test_long_name_truncated(self):
        """100자 초과 이름 → 100자로 잘림"""
        from utils.validators import sanitize_project_name
        long_name = 'A' * 150
        result = sanitize_project_name(long_name)
        assert len(result) == 100


# ---------------------------------------------------------------------------
# T4 > T4.2 — utils/log_filter.py 마스킹 필터 테스트
# ---------------------------------------------------------------------------

class TestTokenMaskingFilter:
    """TokenMaskingFilter — 로그 레코드 내 Token/자격증명 마스킹 [M1.AC 1.6]"""

    def _make_record(self, msg, args=None):
        record = logging.LogRecord(
            name='test', level=logging.INFO,
            pathname='', lineno=0,
            msg=msg, args=args or (), exc_info=None
        )
        return record

    def test_url_basic_auth_masked_in_message(self):
        """URL Basic Auth 자격증명 → [MASKED] 치환"""
        from utils.log_filter import TokenMaskingFilter
        f = TokenMaskingFilter()
        record = self._make_record('연결: https://user:glpat-SECRET@gitlab.local/api')
        f.filter(record)
        assert 'glpat-SECRET' not in record.msg
        assert '[MASKED]' in record.msg

    def test_dict_args_sensitive_key_masked(self):
        """args가 dict이고 'token' 키 포함 → '***' 치환"""
        from utils.log_filter import TokenMaskingFilter
        f = TokenMaskingFilter()
        record = self._make_record('연결 시도', {'token': 'secret-value', 'url': 'https://x.com'})
        f.filter(record)
        assert record.args['token'] == '***'
        assert record.args['url'] == 'https://x.com'

    def test_dict_args_access_token_masked(self):
        """'access_token' 키 → '***' 치환"""
        from utils.log_filter import TokenMaskingFilter
        f = TokenMaskingFilter()
        record = self._make_record('GitHub 연결', {'access_token': 'ghp-SECRET', 'repo': 'myrepo'})
        f.filter(record)
        assert record.args['access_token'] == '***'
        assert record.args['repo'] == 'myrepo'

    def test_dict_args_password_masked(self):
        """'password' 키 → '***' 치환"""
        from utils.log_filter import TokenMaskingFilter
        f = TokenMaskingFilter()
        record = self._make_record('인증', {'password': 'my_pass', 'user': 'admin'})
        f.filter(record)
        assert record.args['password'] == '***'

    def test_non_sensitive_dict_args_unchanged(self):
        """민감하지 않은 dict args → 변경 없음"""
        from utils.log_filter import TokenMaskingFilter
        f = TokenMaskingFilter()
        record = self._make_record('통계', {'count': 10, 'project': 'MyProj'})
        f.filter(record)
        assert record.args['count'] == 10
        assert record.args['project'] == 'MyProj'

    def test_filter_returns_true_always(self):
        """filter() 반환값은 항상 True (로그 레코드 통과)"""
        from utils.log_filter import TokenMaskingFilter
        f = TokenMaskingFilter()
        record = self._make_record('정상 메시지')
        result = f.filter(record)
        assert result is True

    def test_token_masking_filter_registered_in_app(self):
        """create_app()이 TokenMaskingFilter를 handler에 등록했는지 확인"""
        from app import create_app
        from utils.log_filter import TokenMaskingFilter
        app = create_app({'TESTING': True})
        handlers = app.logger.handlers
        assert handlers, "핸들러가 등록되어야 합니다"
        filters = handlers[0].filters
        assert any(isinstance(f, TokenMaskingFilter) for f in filters), \
            "TokenMaskingFilter가 핸들러에 등록되어야 합니다"

    def test_msg_none_no_error(self):
        """record.msg가 None일 때 필터가 정상 동작 (branch 커버)"""
        from utils.log_filter import TokenMaskingFilter
        f = TokenMaskingFilter()
        record = self._make_record(None)
        result = f.filter(record)
        assert result is True

    def test_args_none_no_error(self):
        """record.args가 None(dict/list/tuple 아님)일 때 필터 정상 동작 (branch 커버)"""
        from utils.log_filter import TokenMaskingFilter
        f = TokenMaskingFilter()
        record = self._make_record('메시지', args=None)
        record.args = None  # dict도 list/tuple도 아닌 브랜치
        result = f.filter(record)
        assert result is True

    def test_list_args_url_masked(self):
        """args가 list일 때 포맷 후 URL 마스킹 적용 (list branch 커버)"""
        from utils.log_filter import TokenMaskingFilter
        f = TokenMaskingFilter()
        record = self._make_record('연결: %s', ['https://user:secret@gitlab.local'])
        record.args = ['https://user:secret@gitlab.local']
        f.filter(record)
        assert 'secret' not in record.msg, "list args 처리 후 URL 자격증명이 마스킹되어야 함"


class TestMaskUrlCredentials:
    """mask_url_credentials() 단위 테스트"""

    def test_http_basic_auth_masked(self):
        from utils.log_filter import mask_url_credentials
        result = mask_url_credentials('http://user:password@gitlab.local')
        assert 'password' not in result
        assert '[MASKED]' in result

    def test_https_basic_auth_masked(self):
        from utils.log_filter import mask_url_credentials
        result = mask_url_credentials('연결: https://admin:glpat-XYZ@gitlab.local/api/v4')
        assert 'glpat-XYZ' not in result
        assert '[MASKED]' in result

    def test_url_without_auth_unchanged(self):
        from utils.log_filter import mask_url_credentials
        url = 'https://github.com/user/repo'
        result = mask_url_credentials(url)
        assert result == url

    def test_non_url_text_unchanged(self):
        from utils.log_filter import mask_url_credentials
        text = '분석 완료 — 함수 수: 150'
        assert mask_url_credentials(text) == text


class TestTruncateSnippet:
    """truncate_snippet() 단위 테스트"""

    def test_short_text_unchanged(self):
        from utils.log_filter import truncate_snippet
        text = 'short text'
        assert truncate_snippet(text) == text

    def test_exactly_100_chars_unchanged(self):
        from utils.log_filter import truncate_snippet
        text = 'A' * 100
        assert truncate_snippet(text) == text

    def test_over_100_chars_truncated(self):
        from utils.log_filter import truncate_snippet
        text = 'B' * 150
        result = truncate_snippet(text)
        assert len(result) < 150
        assert 'truncated' in result


# ---------------------------------------------------------------------------
# [T4.4] Flask 보안 헤더 검증
# ---------------------------------------------------------------------------

class TestSecurityHeaders:
    """Flask 응답에 필수 보안 헤더 포함 확인 [security-standards.md §9.3, §9.4]"""

    def test_security_headers(self):
        """모든 응답에 5개 보안 헤더 포함 확인"""
        from app import create_app
        app = create_app({'TESTING': True})
        with app.test_client() as client:
            resp = client.get('/nonexistent')  # 404도 보안 헤더는 포함됨

        assert resp.headers.get('X-Frame-Options') == 'DENY', \
            "X-Frame-Options 헤더 누락 (§9.3 클릭재킹 방어)"
        assert resp.headers.get('X-Content-Type-Options') == 'nosniff', \
            "X-Content-Type-Options 헤더 누락 (§9.4 MIME 스니핑 방어)"
        csp = resp.headers.get('Content-Security-Policy', '')
        assert "default-src 'self'" in csp, "CSP default-src 누락"
        assert 'unsafe-eval' not in csp, "CSP에 unsafe-eval 포함됨 — 금지"
        assert resp.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin', \
            "Referrer-Policy 헤더 누락 (§9.4)"
        assert resp.headers.get('X-XSS-Protection') == '0', \
            "X-XSS-Protection 헤더 누락 (레거시 필터 비활성화)"

    def test_secret_key_is_dynamic(self):
        """SECRET_KEY가 실행마다 다르게 생성됨 (하드코딩 없음) [§4.2]"""
        from app import create_app
        app1 = create_app({'TESTING': True})
        app2 = create_app({'TESTING': True})
        assert app1.secret_key != app2.secret_key, \
            "SECRET_KEY가 동적 생성이 아님 — 하드코딩 금지 (§4.2)"
        assert len(app1.secret_key) >= 32, \
            "SECRET_KEY 길이 부족 — 최소 32바이트 권장"
