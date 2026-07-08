"""
T3 > T3.9 — Flask REST API routes 단위 테스트

[M1.F1] 소스 연결 API
[M1.F3] 전역 검색 API
[M1.F4] 의존성 그래프 API
[M1.F5] 호출 흐름도 API
[M1.F6] SP 흐름도 API
[M1.F7] 분석 시작/진행/결과 API
[M1.F8] Excel 내보내기 API
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    from app import create_app
    return create_app({'TESTING': True})


@pytest.fixture
def client(app):
    return app.test_client()


def _json(resp):
    """응답 JSON 파싱 헬퍼."""
    return resp.get_json()


# ---------------------------------------------------------------------------
# [M1.F1] Source Routes — /api/sources
# ---------------------------------------------------------------------------

class TestGitLabConnect:
    """POST /api/sources/gitlab/connect"""

    def test_returns_projects_on_success(self, client):
        """`_create_gitlab_adapter` 모킹 → 프로젝트 목록 반환 [M1.AC 1.1]"""
        mock_adapter = MagicMock()
        mock_adapter.ssl_warning = ''  # T4.3: GitLabClient 인터페이스 반영
        mock_adapter.list_projects.return_value = [
            {'id': '1', 'name': 'MyProject', 'path': 'group/my-project'}
        ]
        with patch('routes.source_routes._create_gitlab_adapter', return_value=mock_adapter):
            resp = client.post('/api/sources/gitlab/connect',
                               json={'url': 'http://git.local', 'token': 'secret'})
        assert resp.status_code == 200
        data = _json(resp)
        assert 'projects' in data
        assert len(data['projects']) == 1
        assert data['projects'][0]['name'] == 'MyProject'

    def test_missing_url_returns_400(self, client):
        """url 없이 요청 시 400 반환"""
        resp = client.post('/api/sources/gitlab/connect', json={'token': 'tok'})
        assert resp.status_code == 400
        assert 'error' in _json(resp)

    def test_adapter_exception_returns_500(self, client):
        """어댑터 connect() 예외 → 500 반환"""
        mock_adapter = MagicMock()
        mock_adapter.connect.side_effect = RuntimeError('연결 실패')
        with patch('routes.source_routes._create_gitlab_adapter', return_value=mock_adapter):
            resp = client.post('/api/sources/gitlab/connect',
                               json={'url': 'http://git.local', 'token': 'tok'})
        assert resp.status_code == 500
        assert 'error' in _json(resp)

    def test_response_has_request_id(self, client):
        """응답 JSON에 request_id 포함"""
        mock_adapter = MagicMock()
        mock_adapter.list_projects.return_value = []
        with patch('routes.source_routes._create_gitlab_adapter', return_value=mock_adapter):
            resp = client.post('/api/sources/gitlab/connect',
                               json={'url': 'http://git.local', 'token': ''})
        assert 'request_id' in _json(resp)


class TestGitHubConnect:
    """POST /api/sources/github/connect"""

    def test_returns_projects_on_success(self, client):
        """GitHubClient 모킹 → 레포 목록 반환"""
        mock_gh = MagicMock()
        mock_gh.list_projects.return_value = [
            {'id': '100', 'name': 'repo1', 'path': 'user/repo1'}
        ]
        with patch('services.github_client.GitHubClient', return_value=mock_gh):
            resp = client.post('/api/sources/github/connect', json={'token': 'gh_tok'})
        assert resp.status_code == 200
        data = _json(resp)
        assert 'projects' in data

    def test_closed_network_returns_503(self, client):
        """폐쇄망 ConnectionError → 503 반환 [M1.EX-2]"""
        mock_gh = MagicMock()
        mock_gh.connect.side_effect = ConnectionError('폐쇄망 차단')
        with patch('services.github_client.GitHubClient', return_value=mock_gh):
            resp = client.post('/api/sources/github/connect', json={'token': ''})
        assert resp.status_code == 503


class TestLocalValidate:
    """POST /api/sources/local/validate"""

    def test_valid_path_returns_projects(self, client):
        """유효한 로컬 경로 → 프로젝트 정보 반환"""
        mock_local = MagicMock()
        mock_local.list_projects.return_value = [
            {'id': '/local/proj', 'name': 'proj', 'path': '/local/proj'}
        ]
        with patch('services.source_service.LocalFolderManager', return_value=mock_local):
            resp = client.post('/api/sources/local/validate', json={'path': '/local/proj'})
        assert resp.status_code == 200
        assert 'projects' in _json(resp)

    def test_missing_path_returns_400(self, client):
        """path 없이 요청 시 400 반환"""
        resp = client.post('/api/sources/local/validate', json={})
        assert resp.status_code == 400

    def test_invalid_path_returns_400(self, client):
        """존재하지 않는 경로 → 400 반환 [M1.EX-3]"""
        mock_local = MagicMock()
        mock_local.connect.side_effect = FileNotFoundError('폴더 없음')
        with patch('services.source_service.LocalFolderManager', return_value=mock_local):
            resp = client.post('/api/sources/local/validate', json={'path': '/nonexist'})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# [M1.F7] Analyze Routes — /api/analyze
# ---------------------------------------------------------------------------

class TestAnalyzeStart:
    """POST /api/analyze/start"""

    def test_start_returns_200(self, client):
        """유효한 projects → 200 started 반환 [M1.AC 7.1]"""
        with patch('services.analyze_service.start_analysis') as mock_start:
            resp = client.post('/api/analyze/start',
                               json={'projects': [{'name': 'P1', 'id': '1'}]})
        assert resp.status_code == 200
        assert _json(resp)['status'] == 'started'
        mock_start.assert_called_once()

    def test_empty_projects_returns_400(self, client):
        """빈 projects 목록 → 400 반환"""
        resp = client.post('/api/analyze/start', json={'projects': []})
        assert resp.status_code == 400

    def test_missing_projects_returns_400(self, client):
        """projects 키 누락 → 400 반환"""
        resp = client.post('/api/analyze/start', json={})
        assert resp.status_code == 400


class TestAnalyzeProgress:
    """GET /api/analyze/progress"""

    def test_returns_progress_dict(self, client):
        """진행률 dict 반환 [M1.AC 7.2]"""
        mock_progress = {'P1': {'status': '분석 중', 'progress_pct': 50}}
        with patch('services.analyze_service.get_progress', return_value=mock_progress):
            resp = client.get('/api/analyze/progress')
        assert resp.status_code == 200
        data = _json(resp)
        assert 'progress' in data
        assert data['progress']['P1']['status'] == '분석 중'


class TestAnalyzeResults:
    """GET /api/analyze/results"""

    def test_returns_all_results(self, client):
        """분석 결과 캐시 반환"""
        mock_results = {'P1': {'complexity': [], 'sp_calls': []}}
        with patch('services.result_cache.AnalysisResultCache.get_all_results',
                   return_value=mock_results):
            resp = client.get('/api/analyze/results')
        assert resp.status_code == 200
        data = _json(resp)
        assert 'results' in data
        assert 'P1' in data['results']

    def test_empty_cache_returns_empty_results(self, client):
        """빈 캐시 → 빈 results 반환"""
        with patch('services.result_cache.AnalysisResultCache.get_all_results',
                   return_value={}):
            resp = client.get('/api/analyze/results')
        assert resp.status_code == 200
        assert _json(resp)['results'] == {}


# ---------------------------------------------------------------------------
# [M1.F3] Search Routes — /api/search
# ---------------------------------------------------------------------------

class TestSearch:
    """POST /api/search"""

    def test_returns_search_results(self, client):
        """키워드 검색 → 결과 반환 [M1.AC 3.1]"""
        mock_results = {'P1': {'/p/A.cs': [(5, 'ExecuteReader(cmd)')]}}

        with patch('services.result_cache.AnalysisResultCache.get_all_results',
                   return_value={'P1': {'complexity': []}}), \
             patch('services.search_service.search_keyword', return_value=mock_results):
            resp = client.post('/api/search',
                               json={'keyword': 'ExecuteReader', 'regex_mode': False})
        assert resp.status_code == 200
        assert 'results' in _json(resp)

    def test_missing_keyword_returns_400(self, client):
        """keyword 없이 요청 시 400 반환"""
        resp = client.post('/api/search', json={})
        assert resp.status_code == 400

    def test_empty_keyword_returns_400(self, client):
        """빈 keyword → 400 반환"""
        resp = client.post('/api/search', json={'keyword': ''})
        assert resp.status_code == 400

    def test_invalid_regex_returns_400(self, client):
        """유효하지 않은 정규식 → 400 반환"""
        with patch('services.result_cache.AnalysisResultCache.get_all_results',
                   return_value={'P1': {'complexity': []}}), \
             patch('services.search_service.search_keyword',
                   side_effect=ValueError('유효하지 않은 정규식')):
            resp = client.post('/api/search',
                               json={'keyword': '[invalid', 'regex_mode': True})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# [M1.F4][M1.F5][M1.F6] Graph Routes — /api/graph
# ---------------------------------------------------------------------------

class TestDependencyGraph:
    """GET /api/graph/dependency"""

    def test_returns_nodes_and_edges(self, client):
        """의존성 그래프 nodes/edges 반환 [M1.AC 4.1]"""
        mock_results = {
            'P1': {'dependency_graph': {'nodes': ['A', 'B'], 'edges': [['A', 'B']]}}
        }
        with patch('services.result_cache.AnalysisResultCache.get_all_results',
                   return_value=mock_results):
            resp = client.get('/api/graph/dependency')
        assert resp.status_code == 200
        data = _json(resp)
        assert 'nodes' in data and 'edges' in data

    def test_empty_cache_returns_empty_graph(self, client):
        """빈 캐시 → 빈 그래프 반환"""
        with patch('services.result_cache.AnalysisResultCache.get_all_results',
                   return_value={}):
            resp = client.get('/api/graph/dependency')
        assert resp.status_code == 200
        data = _json(resp)
        assert data['nodes'] == [] and data['edges'] == []


class TestFlowClassGraph:
    """GET /api/graph/flow/class"""

    def test_returns_call_graph(self, client):
        """호출 흐름 그래프 반환 [M1.AC 5.1]"""
        mock_results = {
            'P1': {'call_graph': {'nodes': ['ClassA'], 'edges': []}}
        }
        with patch('services.result_cache.AnalysisResultCache.get_all_results',
                   return_value=mock_results):
            resp = client.get('/api/graph/flow/class')
        assert resp.status_code == 200
        assert 'nodes' in _json(resp)


class TestFlowSpGraph:
    """GET /api/graph/flow/sp"""

    def test_returns_sp_calls(self, client):
        """SP 호출 목록 반환 [M1.AC 6.1]"""
        mock_results = {
            'P1': {'sp_calls': [{'sp_name': 'UP_GetPay', 'project': 'P1'}]}
        }
        with patch('services.result_cache.AnalysisResultCache.get_all_results',
                   return_value=mock_results):
            resp = client.get('/api/graph/flow/sp')
        assert resp.status_code == 200
        data = _json(resp)
        assert 'sp_calls' in data
        assert data['sp_calls'][0]['sp_name'] == 'UP_GetPay'


# ---------------------------------------------------------------------------
# [M1.F8] Export Routes — /api/export
# ---------------------------------------------------------------------------

class TestExcelExport:
    """GET /api/export/excel"""

    def test_returns_xlsx_bytes(self, client):
        """분석 결과 있을 때 .xlsx 반환 [M1.AC 8.6]"""
        mock_results = {'P1': {'complexity': []}}
        fake_bytes = b'PK\x03\x04fake_xlsx_content'
        with patch('services.result_cache.AnalysisResultCache.get_all_results',
                   return_value=mock_results), \
             patch('services.export_service.generate_excel_report',
                   return_value=fake_bytes):
            resp = client.get('/api/export/excel')
        assert resp.status_code == 200
        assert b'PK' in resp.data  # ZIP/xlsx 매직 바이트
        assert 'application/vnd.openxmlformats' in resp.content_type

    def test_no_results_returns_404(self, client):
        """분석 결과 없을 때 404 반환"""
        with patch('services.result_cache.AnalysisResultCache.get_all_results',
                   return_value={}):
            resp = client.get('/api/export/excel')
        assert resp.status_code == 404

    def test_filename_has_correct_format(self, client):
        """다운로드 파일명이 payletterCodeLab_Report_{YYYYMMDD_HHMMSS}.xlsx 형식 [M1.AC 8.6]"""
        mock_results = {'P1': {'complexity': []}}
        fake_bytes = b'PK\x03\x04xlsx'
        with patch('services.result_cache.AnalysisResultCache.get_all_results',
                   return_value=mock_results), \
             patch('services.export_service.generate_excel_report',
                   return_value=fake_bytes):
            resp = client.get('/api/export/excel')
        assert resp.status_code == 200
        content_disp = resp.headers.get('Content-Disposition', '')
        assert 'payletterCodeLab_Report_' in content_disp
        assert '.xlsx' in content_disp

    def test_generate_exception_returns_500(self, client):
        """generate_excel_report 예외 → 500 반환"""
        with patch('services.result_cache.AnalysisResultCache.get_all_results',
                   return_value={'P1': {'complexity': []}}), \
             patch('services.export_service.generate_excel_report',
                   side_effect=RuntimeError('생성 실패')):
            resp = client.get('/api/export/excel')
        assert resp.status_code == 500
        assert 'error' in _json(resp)


# ---------------------------------------------------------------------------
# 추가 커버리지 보강 — 미커버 경로
# ---------------------------------------------------------------------------

class TestSourceRoutesAdditional:
    """source_routes 미커버 경로 보강"""

    def test_gitlab_connect_uses_factory(self, client):
        """`_create_gitlab_adapter` 함수 본체 실행 확인 (app.get_gitlab_adapter 패칭)"""
        mock_adapter = MagicMock()
        mock_adapter.ssl_warning = ''  # T4.3: GitLabClient 인터페이스 반영
        mock_adapter.list_projects.return_value = []
        with patch('app.get_gitlab_adapter', return_value=mock_adapter):
            resp = client.post('/api/sources/gitlab/connect',
                               json={'url': 'http://git.local', 'token': 'tok'})
        assert resp.status_code == 200

    def test_local_validate_generic_exception_returns_500(self, client):
        """LocalFolderManager 일반 예외 → 500 반환"""
        mock_local = MagicMock()
        mock_local.connect.side_effect = RuntimeError('알 수 없는 오류')
        with patch('services.source_service.LocalFolderManager', return_value=mock_local):
            resp = client.post('/api/sources/local/validate', json={'path': '/some/path'})
        assert resp.status_code == 500
        assert 'error' in _json(resp)


class TestSearchRoutesAdditional:
    """search_routes 미커버 경로 보강"""

    def test_build_project_files_reads_existing_files(self, client, tmp_path):
        """`_build_project_files` 파일 읽기 경로 실행 — 실제 파일 존재 시"""
        cs_file = tmp_path / 'Test.cs'
        cs_file.write_text('class Test {}', encoding='utf-8')
        results_cache = {
            'P1': {'complexity': [{'file_path': str(cs_file)}]}
        }
        mock_search_result = {}
        with patch('services.result_cache.AnalysisResultCache.get_all_results',
                   return_value=results_cache), \
             patch('services.search_service.search_keyword',
                   return_value=mock_search_result):
            resp = client.post('/api/search', json={'keyword': 'class'})
        assert resp.status_code == 200

    def test_build_project_files_handles_oserror(self, client):
        """`_build_project_files` — OSError 무시 후 계속 진행"""
        results_cache = {
            'P1': {'complexity': [{'file_path': '/nonexistent/file.cs'}]}
        }
        with patch('services.result_cache.AnalysisResultCache.get_all_results',
                   return_value=results_cache), \
             patch('services.search_service.search_keyword', return_value={}):
            resp = client.post('/api/search', json={'keyword': 'test'})
        assert resp.status_code == 200

    def test_search_generic_exception_returns_500(self, client):
        """search_keyword 일반 예외 → 500 반환"""
        with patch('services.result_cache.AnalysisResultCache.get_all_results',
                   return_value={'P1': {'complexity': []}}), \
             patch('services.search_service.search_keyword',
                   side_effect=RuntimeError('검색 오류')):
            resp = client.post('/api/search', json={'keyword': 'test'})
        assert resp.status_code == 500
