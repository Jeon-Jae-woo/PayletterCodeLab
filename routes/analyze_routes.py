"""
분석 실행·진행률·결과 API — [M1.F7]

비동기 분석 시작, SSE/폴링 진행률, 분석 결과 반환.
라우트는 순수 위임만 담당 — 비즈니스 로직 없음.
"""
from flask import Blueprint, g, jsonify, request

analyze_bp = Blueprint('analyze_bp', __name__, url_prefix='/api/analyze')


@analyze_bp.route('/start', methods=['POST'])
def start_analysis():
    """POST /api/analyze/start — 선택한 프로젝트 비동기 분석 시작 [M1.AC 7.1]."""
    data = request.get_json() or {}
    projects = data.get('projects', [])
    if not projects:
        return jsonify({'error': 'projects 목록이 필요합니다', 'request_id': g.request_id}), 400
    from services import analyze_service
    analyze_service.start_analysis(projects)
    return jsonify({'status': 'started', 'request_id': g.request_id})


@analyze_bp.route('/progress', methods=['GET'])
def get_progress():
    """GET /api/analyze/progress — 분석 진행 상태 반환 [M1.AC 7.2]."""
    from services import analyze_service
    progress = analyze_service.get_progress()
    return jsonify({'progress': progress, 'request_id': g.request_id})


@analyze_bp.route('/results', methods=['GET'])
def get_results():
    """GET /api/analyze/results — 전체 분석 결과 반환 [M1.AC 7.3]."""
    from services.result_cache import AnalysisResultCache
    results = AnalysisResultCache.get_all_results()
    return jsonify({'results': results, 'request_id': g.request_id})


@analyze_bp.route('/results/<path:project_name>', methods=['DELETE'])
def remove_result(project_name: str):
    """DELETE /api/analyze/results/<project_name> — 특정 프로젝트 캐시 제거."""
    from services.result_cache import AnalysisResultCache
    removed = AnalysisResultCache.remove(project_name)
    if not removed:
        return jsonify({'error': '해당 프로젝트를 찾을 수 없습니다', 'request_id': g.request_id}), 404
    return jsonify({'status': 'removed', 'project': project_name, 'request_id': g.request_id})
