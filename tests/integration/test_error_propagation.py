"""
[M1.IT-5] Sad — GitLab 인증 실패 → 오류 전파
[M1.IT-6] Sad — GitHub 네트워크 차단 → 로컬 대체 안내

Ref: PRD Section 5-2 [M1.IT-5], [M1.IT-6]
커버 AC: [M1.AC 1.7], [M1.AC 1.8]
커버 EX: [M1.EX-1], [M1.EX-2]
"""
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# [M1.IT-5] Sad — GitLab 인증 실패 전파
# ---------------------------------------------------------------------------

@pytest.mark.sad
class TestGitLabAuthFailure:
    """[M1.IT-5] GitLab 인증 실패 오류 전파 통합 테스트 [M1.EX-1]."""

    def test_gitlab_auth_failure(self, client):
        """
        MockGitLab 어댑터 → PermissionError(401) → 라우트 401 응답.

        검증:
        1. HTTP 401 또는 400 반환
        2. 응답 JSON {error: "<non-empty>"} 포함
        3. AnalysisResultCache에 데이터 미저장 확인
        4. 서버 500 에러 미발생 (안전한 오류 처리)
        """
        # 전제조건: MockGitLab 어댑터 → PermissionError 발생 설정 [M1.EX-1]
        mock_adapter = MagicMock()
        mock_adapter.connect.side_effect = PermissionError(
            '[M1.EX-1] GitLab 인증 실패: 유효하지 않은 Personal Access Token'
        )

        with patch('routes.source_routes._create_gitlab_adapter', return_value=mock_adapter):
            resp = client.post(
                '/api/sources/gitlab/connect',
                json={'url': 'http://mock.local', 'token': 'invalid-token'},
            )

        # 1. HTTP 401 반환 확인
        assert resp.status_code in (400, 401), (
            f'인증 실패 시 400/401이어야 합니다. 실제: {resp.status_code}'
        )

        # 2. 응답 JSON error 필드 비어있지 않음
        data = resp.get_json()
        assert 'error' in data, 'error 필드가 응답에 없습니다'
        assert data['error'], 'error 필드가 비어 있습니다'

        # 3. AnalysisResultCache 미저장 확인
        from services.result_cache import AnalysisResultCache
        cached = AnalysisResultCache.get_all_results()
        assert len(cached) == 0, (
            f'인증 실패 후 캐시에 데이터가 있습니다: {list(cached.keys())}'
        )

        # 4. 서버 500 에러 미발생
        assert resp.status_code != 500, '인증 실패가 서버 500 오류로 처리됨 — 안전한 오류 처리 필요'

    def test_gitlab_connect_missing_url_returns_400(self, client):
        """URL 없이 연결 시도 → 400 반환 (입력 검증 [M1.AC 1.1])."""
        resp = client.post(
            '/api/sources/gitlab/connect',
            json={'token': 'some-token'},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data


# ---------------------------------------------------------------------------
# [M1.IT-6] Sad — GitHub 네트워크 차단 → 로컬 대체 안내
# ---------------------------------------------------------------------------

@pytest.mark.sad
class TestGitHubNetworkBlocked:
    """[M1.IT-6] GitHub 네트워크 차단 → 로컬 대체 안내 통합 테스트 [M1.EX-2]."""

    def test_github_network_blocked(self, client):
        """
        MockGitHub 어댑터 → _check_network=False → ConnectionError → 503 + redirect_to.

        검증:
        1. HTTP 422 또는 503 반환 (네트워크 오류 명시)
        2. 응답 JSON {redirect_to: "/setup?tab=local"} 필드 포함
        3. 오류 메시지: GitHub 네트워크 차단 안내 문구 포함
        4. 서버 500 에러 미발생
        """
        # 전제조건: GitHubClient._check_network → False (폐쇄망 감지) [M1.EX-2]
        with patch(
            'services.github_client.GitHubClient._check_network',
            return_value=False,
        ):
            resp = client.post(
                '/api/sources/github/connect',
                json={'token': ''},
            )

        # 1. HTTP 503 반환 확인
        assert resp.status_code in (422, 503), (
            f'GitHub 차단 시 422/503이어야 합니다. 실제: {resp.status_code}'
        )

        data = resp.get_json()

        # 2. redirect_to 필드 포함 확인
        assert 'redirect_to' in data, (
            f'redirect_to 필드가 응답에 없습니다. 응답: {data}'
        )
        assert data['redirect_to'] == '/setup?tab=local', (
            f'redirect_to 값이 다릅니다: {data["redirect_to"]}'
        )

        # 3. 오류 메시지 GitHub 차단 안내 포함
        assert 'error' in data
        error_msg = data['error']
        assert error_msg, 'error 메시지가 비어 있습니다'
        # GitHub 차단 관련 키워드 확인
        assert any(
            kw in error_msg for kw in ['GitHub', 'github', '차단', '폐쇄망', 'ConnectionError', 'M1.EX-2']
        ), f'GitHub 차단 안내 문구가 없습니다: {error_msg}'

        # 4. 서버 500 에러 미발생
        assert resp.status_code != 500, 'GitHub 차단이 서버 500 오류로 처리됨'

        # AnalysisResultCache 미저장 확인
        from services.result_cache import AnalysisResultCache
        cached = AnalysisResultCache.get_all_results()
        assert len(cached) == 0, f'차단 오류 후 캐시에 데이터가 있습니다: {list(cached.keys())}'
