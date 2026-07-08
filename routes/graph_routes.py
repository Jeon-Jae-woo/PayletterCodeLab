"""
그래프 데이터 API — [M1.F4] 의존성, [M1.F5] 호출흐름, [M1.F6] SP흐름

분석 결과 캐시에서 그래프 데이터를 집계하여 반환.
라우트는 순수 위임만 담당 — 비즈니스 로직 없음.
"""
from flask import Blueprint, g, jsonify

graph_bp = Blueprint('graph_bp', __name__, url_prefix='/api/graph')


def _get_all_results() -> dict:
    from services.result_cache import AnalysisResultCache
    return AnalysisResultCache.get_all_results()


@graph_bp.route('/dependency', methods=['GET'])
def dependency():
    """GET /api/graph/dependency — 프로젝트 간 의존성 그래프 [M1.AC 4.1]."""
    results = _get_all_results()
    nodes, edges = [], []
    for result in results.values():
        dg = result.get('dependency_graph', {})
        nodes.extend(dg.get('nodes', []))
        edges.extend(dg.get('edges', []))
    return jsonify({'nodes': nodes, 'edges': edges, 'request_id': g.request_id})


@graph_bp.route('/flow/class', methods=['GET'])
def flow_class():
    """GET /api/graph/flow/class — 파일/클래스 간 호출 흐름 [M1.AC 5.1]."""
    results = _get_all_results()
    nodes, edges = [], []
    for result in results.values():
        cg = result.get('call_graph', {})
        nodes.extend(cg.get('nodes', []))
        # flow_analyzer는 caller/callee 키 사용, JS(D3)는 source/target 기대 — 변환
        for e in cg.get('edges', []):
            edges.append({'source': e.get('caller', ''), 'target': e.get('callee', '')})
    return jsonify({'nodes': nodes, 'edges': edges, 'request_id': g.request_id})


@graph_bp.route('/flow/sp', methods=['GET'])
def flow_sp():
    """GET /api/graph/flow/sp — SP 호출 계층 데이터 [M1.AC 6.1]."""
    results = _get_all_results()
    sp_calls = []
    for result in results.values():
        sp_calls.extend(result.get('sp_calls', []))
    return jsonify({'sp_calls': sp_calls, 'request_id': g.request_id})
