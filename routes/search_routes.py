"""
전역 키워드·SP 검색 API — [M1.F3]

분석 결과 캐시에서 파일 경로를 추출하여 실제 파일을 검색.
라우트는 순수 위임만 담당 — 비즈니스 로직 없음.
"""
from flask import Blueprint, g, jsonify, request

from utils import response_helper

search_bp = Blueprint('search_bp', __name__, url_prefix='/api/search')


def _build_project_files(results_cache: dict) -> dict:
    """분석 결과 캐시에서 {project: {file_path: content}} 구조 구성."""
    project_files = {}
    for proj_name, result in results_cache.items():
        files = {}
        for fn in result.get('complexity', []):
            fp = fn.get('file_path', '')
            if fp and fp not in files:
                try:
                    with open(fp, 'r', encoding='utf-8', errors='replace') as f:
                        files[fp] = f.read()
                except OSError:
                    pass
        project_files[proj_name] = files
    return project_files


@search_bp.route('', methods=['POST'])
def search():
    """POST /api/search — 전역 키워드/SP명 검색 [M1.AC 3.1]."""
    data = request.get_json() or {}
    keyword = data.get('keyword', '').strip()
    regex_mode = bool(data.get('regex_mode', False))
    if not keyword:
        return jsonify({'error': 'keyword 필드가 필요합니다', 'request_id': g.request_id}), 400
    try:
        from services import search_service
        from services.result_cache import AnalysisResultCache
        project_files = _build_project_files(AnalysisResultCache.get_all_results())
        results = search_service.search_keyword(keyword, project_files, regex_mode)
        return jsonify({'results': results, 'request_id': g.request_id})
    except ValueError as exc:
        return response_helper.error_response(str(exc), 400, exc)
    except Exception as exc:
        return response_helper.error_response(str(exc), 500, exc)
