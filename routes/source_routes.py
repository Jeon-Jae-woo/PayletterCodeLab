"""
소스 저장소 연결·목록 API — [M1.F1]

GitLab / GitHub / 로컬 폴더 연결 엔드포인트.
라우트는 순수 위임만 담당 — 비즈니스 로직 없음.
Token은 어댑터 인스턴스 내 메모리에만 보관 ([PR-6]).
"""
from flask import Blueprint, g, jsonify, request

from utils import response_helper

source_bp = Blueprint('source_bp', __name__, url_prefix='/api/sources')

# GitHub 어댑터 인스턴스 — 분석 시 클론에 재사용 (토큰은 어댑터 내부 메모리에만 보관)
_github_adapter = None


def get_github_adapter():
    """저장된 GitHub 어댑터 반환. 미연결 시 None."""
    return _github_adapter


def _create_gitlab_adapter():
    """GitLab 어댑터 생성 — 환경에 따라 Mock/실제 선택 (Composition Root 위임)."""
    from app import get_gitlab_adapter
    return get_gitlab_adapter()


@source_bp.route('/gitlab/connect', methods=['POST'])
def gitlab_connect():
    """POST /api/sources/gitlab/connect — GitLab 연결 + 프로젝트 목록 반환."""
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    token = data.get('token', '').strip()
    verify_ssl = bool(data.get('verify_ssl', True))
    if not url:
        return jsonify({'error': 'url 필드가 필요합니다', 'request_id': g.request_id}), 400
    try:
        adapter = _create_gitlab_adapter()
        adapter.connect(url=url, token=token, verify_ssl=verify_ssl)
        projects = adapter.list_projects()
        response = {'projects': projects, 'request_id': g.request_id}
        # SSL 검증 비활성화 경고 포함 [M1.AC 1.7]
        ssl_warning = getattr(adapter, 'ssl_warning', '')
        if ssl_warning:
            response['ssl_warning'] = ssl_warning
        return jsonify(response)
    except PermissionError as exc:
        # [M1.EX-1] GitLab 인증 실패 — 401 반환 (인증 에러는 서버 오류가 아닌 클라이언트 오류)
        return jsonify({'error': str(exc), 'request_id': g.request_id}), 401
    except Exception as exc:
        return response_helper.error_response(str(exc), 500, exc)


@source_bp.route('/github/connect', methods=['POST'])
def github_connect():
    """POST /api/sources/github/connect — GitHub 연결 + 레포지터리 목록 반환."""
    global _github_adapter
    data = request.get_json() or {}
    token = data.get('token', '').strip()
    try:
        from services.github_client import GitHubClient
        adapter = GitHubClient()
        adapter.connect(token=token)
        projects = adapter.list_projects()
        # 어댑터 저장 — 이후 analyze_service 클론 단계에서 재사용
        _github_adapter = adapter
        return jsonify({'projects': projects, 'request_id': g.request_id})
    except ConnectionError as exc:
        # [M1.EX-2] 폐쇄망 차단 — 로컬 폴더 대체 안내 포함 [M1.AC 1.8]
        return jsonify({
            'error': str(exc),
            'redirect_to': '/setup?tab=local',
            'request_id': g.request_id,
        }), 503
    except Exception as exc:
        return response_helper.error_response(str(exc), 500, exc)


@source_bp.route('/local/validate', methods=['POST'])
def local_validate():
    """POST /api/sources/local/validate — 로컬 폴더 경로 유효성 검증."""
    data = request.get_json() or {}
    path = data.get('path', '').strip()
    if not path:
        return jsonify({'error': 'path 필드가 필요합니다', 'request_id': g.request_id}), 400
    try:
        from services.source_service import LocalFolderManager
        adapter = LocalFolderManager()
        adapter.connect(path=path)
        projects = adapter.list_projects()
        return jsonify({'projects': projects, 'request_id': g.request_id})
    except (FileNotFoundError, ValueError) as exc:
        # [M1.EX-3] 경로 오류 — 사용자 안내 메시지 포함
        return response_helper.error_response(str(exc), 400, exc)
    except Exception as exc:
        return response_helper.error_response(str(exc), 500, exc)
