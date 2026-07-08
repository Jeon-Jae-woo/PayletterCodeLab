"""
Excel 내보내기 API — [M1.F8]

분석 결과를 openpyxl로 Excel 파일 생성 후 스트리밍 다운로드.
파일명 형식: payletterCodeLab_Report_{YYYYMMDD_HHMMSS}.xlsx [M1.AC 8.6]
"""
import io
from datetime import datetime

from flask import Blueprint, g, jsonify, send_file

from utils import response_helper

export_bp = Blueprint('export_bp', __name__, url_prefix='/api/export')


@export_bp.route('/excel', methods=['GET'])
def excel():
    """GET /api/export/excel — Excel 보고서 생성 + 스트리밍 다운로드 [M1.AC 8.6]."""
    from services.result_cache import AnalysisResultCache
    from services import export_service
    results = AnalysisResultCache.get_all_results()
    if not results:
        return jsonify({
            'error': '분석 결과가 없습니다. 먼저 분석을 실행하세요.',
            'request_id': g.request_id,
        }), 404
    try:
        excel_bytes = export_service.generate_excel_report(results)
        filename = 'payletterCodeLab_Report_{}.xlsx'.format(
            datetime.now().strftime('%Y%m%d_%H%M%S')
        )
        return send_file(
            io.BytesIO(excel_bytes),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        return response_helper.error_response(str(exc), 500, exc)
