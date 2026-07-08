"""
PGAnalyzer Flask 앱 팩토리 + PyInstaller 진입점

[PR-4] Flask 3.x 앱 팩토리 패턴
[PR-5] JSON 구조화 로거 (timestamp/level/message/context)
[M1.EX-8] 포트 자동 탐색 (5000 → 5001 → ...)
"""
import json
import logging
import secrets
import socket
import threading
import uuid
import webbrowser
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from flask import Flask, g

if TYPE_CHECKING:
    from services.source_service import SourceManager


class JsonFormatter(logging.Formatter):
    """
    [PR-5] ISO 8601 UTC JSON 구조화 로그 포매터.
    필드: timestamp, level, message, context(request_id, correlation_id)
    보안: token/access_token 등 민감 키는 로그에서 제거해야 함 (T4.2에서 마스킹 추가).
    """

    def format(self, record):
        log_record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'context': getattr(record, 'context', {}),
        }
        return json.dumps(log_record, ensure_ascii=False)


def find_available_port(start_port: int = 5000, max_tries: int = 10) -> int:
    """
    [M1.EX-8] 포트 자동 탐색 — start_port부터 시작해 max_tries번 시도.
    사용 가능한 첫 번째 포트를 반환하며, 모두 점유 시 OSError 발생.
    """
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(('', port))
                return port
            except OSError:
                continue
    raise OSError(
        f"포트 {start_port}~{start_port + max_tries - 1} 범위 내 사용 가능한 포트 없음"
    )


def create_app(config=None) -> Flask:
    """
    Flask 앱 팩토리. Blueprint 등록 + 로거 설정 + 미들웨어 바인딩.
    PyInstaller 번들 및 개발 서버 모두 이 팩토리를 통해 앱 생성.
    """
    app = Flask(__name__)

    # SECRET_KEY 동적 생성 — 하드코딩 금지 ([T4.4], security-standards.md §4.2)
    app.secret_key = secrets.token_hex(32)

    # 외부 설정 주입 (테스트/운영 분기)
    if config:
        app.config.update(config)

    # Jinja2 자동 이스케이핑 활성화 — XSS 방어 (security-standards.md §9.1)
    app.jinja_env.autoescape = True

    _setup_logging(app)
    _register_blueprints(app)
    _register_middleware(app)

    return app


def _setup_logging(app):
    """JSON 구조화 로거를 Flask 앱 logger에 바인딩 + Token 마스킹 필터 등록."""
    from utils.log_filter import TokenMaskingFilter
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(TokenMaskingFilter())
    app.logger.handlers = [handler]
    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False


def _register_blueprints(app):
    """[PR-4] Blueprint 동적 등록. 각 Blueprint는 routes/ 하위 모듈에 정의."""
    from routes.page_routes import page_bp
    from routes.source_routes import source_bp
    from routes.analyze_routes import analyze_bp
    from routes.search_routes import search_bp
    from routes.graph_routes import graph_bp
    from routes.export_routes import export_bp

    app.register_blueprint(page_bp)
    app.register_blueprint(source_bp)
    app.register_blueprint(analyze_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(graph_bp)
    app.register_blueprint(export_bp)


def _register_middleware(app):
    """request_id 생성 + X-Request-ID 응답 헤더 추가 + 보안 헤더 미들웨어."""

    @app.before_request
    def _set_request_id():
        # UUID4로 요청별 고유 ID 생성 — 로그 correlation용
        g.request_id = str(uuid.uuid4())

    @app.after_request
    def _add_request_id_header(response):
        response.headers['X-Request-ID'] = getattr(g, 'request_id', '')
        return response

    @app.after_request
    def _add_security_headers(response):
        # 클릭재킹 방지 — iframe 임베딩 차단 (security-standards.md §9.3)
        response.headers['X-Frame-Options'] = 'DENY'
        # MIME 타입 스니핑 방지 — Content-Type 위장 공격 차단 (security-standards.md §9.4)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # CSP — 외부 CDN 로드 차단, 로컬 번들 전용 (security-standards.md §9.4)
        # script-src 'unsafe-inline': Jinja2 템플릿 인라인 <script> 및 onclick 핸들러 허용
        # 단일 사용자 로컬 도구 — 외부 노출 없음, 사용자 생성 콘텐츠 없음 (decision_log 기록)
        # style-src 'unsafe-inline': Tailwind 유틸리티 클래스 지원 (decision_log 기록)
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:"
        )
        # Referrer 정책 — 크로스 오리진 요청 시 origin만 전송 (security-standards.md §9.4)
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # 레거시 XSS 필터 비활성화 — CSP로 대체, 레거시 필터 오동작 방지 (security-standards.md §9.4)
        response.headers['X-XSS-Protection'] = '0'
        return response


def get_gitlab_adapter() -> 'SourceManager':
    """
    Composition Root — GITLAB_MOCK 환경 변수에 따라 GitLab 어댑터 선택.
    GITLAB_MOCK=true  → GitLabMockClient (로컬 개발, 네트워크 없이 동작)
    GITLAB_MOCK=false → GitLabClient    (production, 사설망 GitLab 연결)
    [PR-3] EnvironmentDivergence port-adapter 계약 구현.
    """
    from config import get_config
    cfg = get_config()
    if cfg['GITLAB_MOCK']:
        from services.gitlab_mock import GitLabMockClient
        return GitLabMockClient()
    from services.gitlab_client import GitLabClient
    return GitLabClient()


if __name__ == '__main__':
    # PyInstaller 진입점 — .exe 더블클릭 실행 시 진입
    port = find_available_port()
    app = create_app()

    def _open_browser():
        """Flask 서버 준비 후 2초 대기, 브라우저 자동 오픈."""
        import time
        time.sleep(2)
        webbrowser.open(f'http://localhost:{port}')

    threading.Thread(target=_open_browser, daemon=True).start()
    app.run(host='127.0.0.1', port=port, debug=False)
