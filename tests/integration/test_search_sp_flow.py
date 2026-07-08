"""
[M1.IT-2] Happy — 전역 검색 → SP 흐름도 딥링크 연동

Ref: PRD Section 5-2 [M1.IT-2]
커버 AC: [M1.AC 3.1], [M1.AC 6.5]

전제조건: 분석 완료 상태 (preloaded_cache fixture로 캐시 사전 로드)
"""
import pytest


@pytest.mark.happy
class TestSearchToSpDeeplink:
    """[M1.IT-2] 전역 검색 → SP 흐름도 딥링크 체인 통합 테스트."""

    def test_search_to_sp_deeplink(self, client, preloaded_cache):
        """
        POST /api/search {keyword: "PaymentSP"} → SP명 포함 결과
        → GET /api/graph/flow/sp → sp_calls 포함 확인 (딥링크 체인).

        검증:
        1. POST /api/search → HTTP 200, 결과에 PaymentSP 키워드 포함
        2. GET /api/graph/flow/sp → HTTP 200, sp_calls 포함
        3. 검색 결과 SP명으로 /api/graph/flow/sp 응답 정상 (딥링크 체인 확인)
        """
        # 1. POST /api/search — SP명 키워드 검색 [M1.AC 3.1]
        resp = client.post('/api/search', json={'keyword': 'PaymentSP'})
        assert resp.status_code == 200
        search_data = resp.get_json()
        assert 'results' in search_data

        # 검색 결과 구조: {project_name: {file_path: [[line_no, snippet]]}}
        results = search_data['results']
        assert len(results) > 0, '검색 결과가 비어 있습니다'

        # PaymentSP가 검색 결과 어딘가에 포함되는지 확인
        found_sp = False
        for project_hits in results.values():
            for file_hits in (project_hits.values() if isinstance(project_hits, dict) else [project_hits]):
                for hit in (file_hits if isinstance(file_hits, list) else []):
                    # hit: [line_no, snippet] 구조
                    snippet = hit[1] if isinstance(hit, list) and len(hit) > 1 else str(hit)
                    if 'PaymentSP' in snippet:
                        found_sp = True
                        break
        assert found_sp, (
            f'검색 결과에 PaymentSP가 없습니다. 결과 구조: {results}'
        )

        # 2. GET /api/graph/flow/sp — sp_calls 포함 확인
        resp2 = client.get('/api/graph/flow/sp')
        assert resp2.status_code == 200
        sp_data = resp2.get_json()
        assert 'sp_calls' in sp_data
        sp_calls = sp_data['sp_calls']
        assert isinstance(sp_calls, list)
        assert len(sp_calls) > 0, 'sp_calls 목록이 비어 있습니다'

        # 3. 딥링크 체인 확인 — 검색 결과의 SP명으로 /api/graph/flow/sp 조회 [M1.AC 6.5]
        sp_names_in_flow = {call['sp_name'] for call in sp_calls}
        assert 'PaymentSP' in sp_names_in_flow, (
            f'SP 흐름도에 PaymentSP가 없습니다. 실제: {sp_names_in_flow}'
        )

    def test_search_empty_keyword_returns_400(self, client, preloaded_cache):
        """빈 키워드 검색 → 400 반환 [M1.AC 3.1]."""
        resp = client.post('/api/search', json={'keyword': ''})
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data

    def test_sp_flow_empty_when_no_cache(self, client):
        """캐시 없을 때 /api/graph/flow/sp → sp_calls 빈 리스트 반환."""
        # clear_analysis_cache autouse fixture가 캐시를 비운 상태
        resp = client.get('/api/graph/flow/sp')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['sp_calls'] == []
