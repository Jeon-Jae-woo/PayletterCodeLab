"""
T1 > T1.4 Flask 앱 팩토리·Blueprint·로깅 설정 검증 테스트

[PR-4] Flask 3.x, [PR-5] 로그 구조, [M1.EX-8] 포트 자동 탐색 검증.
"""
import json
import logging
import socket
import sys
import os
import unittest.mock as mock

# PGAnalyzer 루트를 sys.path에 추가 (직접 모듈 임포트용)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestCreateApp:
    """create_app() 팩토리 패턴 검증 [Normal 시나리오]"""

    def test_create_app_returns_flask_app(self):
        """create_app()이 Flask 인스턴스를 반환해야 함"""
        from flask import Flask
        from app import create_app
        app = create_app()
        assert isinstance(app, Flask), "create_app()이 Flask 앱을 반환하지 않습니다"

    def test_create_app_with_test_config(self):
        """테스트 설정 주입 가능해야 함"""
        from app import create_app
        app = create_app({'TESTING': True})
        assert app.config['TESTING'] is True

    def test_create_app_registers_source_blueprint(self):
        """source_bp Blueprint가 등록되어야 함"""
        from app import create_app
        app = create_app()
        assert 'source_bp' in app.blueprints, "source_bp Blueprint가 등록되지 않았습니다"

    def test_create_app_registers_analyze_blueprint(self):
        """analyze_bp Blueprint가 등록되어야 함"""
        from app import create_app
        app = create_app()
        assert 'analyze_bp' in app.blueprints, "analyze_bp Blueprint가 등록되지 않았습니다"

    def test_create_app_registers_search_blueprint(self):
        """search_bp Blueprint가 등록되어야 함"""
        from app import create_app
        app = create_app()
        assert 'search_bp' in app.blueprints, "search_bp Blueprint가 등록되지 않았습니다"

    def test_create_app_registers_export_blueprint(self):
        """export_bp Blueprint가 등록되어야 함"""
        from app import create_app
        app = create_app()
        assert 'export_bp' in app.blueprints, "export_bp Blueprint가 등록되지 않았습니다"


class TestJsonLogger:
    """JSON 구조화 로거 검증 [Normal 시나리오] — [PR-5]"""

    def test_json_formatter_emits_timestamp(self):
        """로그 레코드에 timestamp 필드 존재"""
        from app import JsonFormatter
        formatter = JsonFormatter()
        record = logging.LogRecord('test', logging.INFO, '', 0, 'test msg', (), None)
        output = json.loads(formatter.format(record))
        assert 'timestamp' in output, "로그에 timestamp 필드 없음"

    def test_json_formatter_emits_level(self):
        """로그 레코드에 level 필드 존재"""
        from app import JsonFormatter
        formatter = JsonFormatter()
        record = logging.LogRecord('test', logging.INFO, '', 0, 'test msg', (), None)
        output = json.loads(formatter.format(record))
        assert 'level' in output, "로그에 level 필드 없음"
        assert output['level'] == 'INFO'

    def test_json_formatter_emits_message(self):
        """로그 레코드에 message 필드 존재"""
        from app import JsonFormatter
        formatter = JsonFormatter()
        record = logging.LogRecord('test', logging.INFO, '', 0, 'hello world', (), None)
        output = json.loads(formatter.format(record))
        assert 'message' in output, "로그에 message 필드 없음"
        assert output['message'] == 'hello world'

    def test_json_formatter_emits_context(self):
        """로그 레코드에 context 필드 존재"""
        from app import JsonFormatter
        formatter = JsonFormatter()
        record = logging.LogRecord('test', logging.INFO, '', 0, 'ctx test', (), None)
        output = json.loads(formatter.format(record))
        assert 'context' in output, "로그에 context 필드 없음"

    def test_json_formatter_output_is_valid_json(self):
        """로그 출력이 유효한 JSON이어야 함"""
        from app import JsonFormatter
        formatter = JsonFormatter()
        record = logging.LogRecord('test', logging.WARNING, '', 0, 'warn msg', (), None)
        output_str = formatter.format(record)
        # json.loads가 예외 없이 파싱되면 유효한 JSON
        parsed = json.loads(output_str)
        assert isinstance(parsed, dict)

    def test_json_formatter_timestamp_is_iso8601(self):
        """timestamp 필드가 ISO 8601 UTC 형식이어야 함"""
        from app import JsonFormatter
        import re
        formatter = JsonFormatter()
        record = logging.LogRecord('test', logging.INFO, '', 0, 'ts test', (), None)
        output = json.loads(formatter.format(record))
        # ISO 8601 UTC: 예) 2026-06-26T00:00:00.000000+00:00 또는 ...Z
        iso_pattern = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
        assert iso_pattern.match(output['timestamp']), \
            f"timestamp가 ISO 8601 형식이 아닙니다: {output['timestamp']}"


class TestPortDiscovery:
    """[M1.EX-8] 포트 자동 탐색 검증 [Normal/Exception 시나리오]"""

    def test_port_discovery_returns_available_port(self):
        """사용 가능한 포트를 반환해야 함"""
        from app import find_available_port
        port = find_available_port(start_port=19000)
        assert isinstance(port, int), "find_available_port()가 정수를 반환하지 않습니다"
        assert 19000 <= port < 19010, f"반환된 포트 {port}가 범위를 벗어납니다"

    def test_port_discovery_skips_busy_port(self):
        """사용 중인 포트를 건너뛰어야 함 — [M1.EX-8]"""
        from app import find_available_port
        # 특정 포트를 직접 점유하여 skip 동작 검증
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            occupied.bind(('', 19100))
            result = find_available_port(start_port=19100, max_tries=5)
            assert result != 19100, "점유된 포트 19100을 반환해서는 안 됩니다"
            assert result > 19100, f"다음 포트({result})를 반환해야 합니다"

    def test_port_discovery_raises_when_all_busy(self):
        """모든 포트가 사용 중이면 OSError를 발생시켜야 함"""
        from app import find_available_port
        with mock.patch('app.socket.socket') as mock_socket_cls:
            mock_sock = mock.MagicMock()
            mock_sock.__enter__ = mock.MagicMock(return_value=mock_sock)
            mock_sock.__exit__ = mock.MagicMock(return_value=False)
            mock_sock.bind.side_effect = OSError("주소 사용 중")
            mock_socket_cls.return_value = mock_sock
            try:
                find_available_port(start_port=9999, max_tries=3)
                raise AssertionError("OSError가 발생해야 합니다")
            except OSError:
                pass  # 예상된 동작

    def test_port_discovery_default_start_port(self):
        """기본 탐색 포트는 5000이어야 함"""
        from app import find_available_port
        import inspect
        sig = inspect.signature(find_available_port)
        assert sig.parameters['start_port'].default == 5000, \
            "find_available_port의 기본 start_port가 5000이어야 합니다"


class TestRequestIdMiddleware:
    """request_id 미들웨어 + X-Request-ID 헤더 검증 [Normal 시나리오]"""

    def test_response_has_x_request_id_header(self):
        """모든 응답에 X-Request-ID 헤더가 있어야 함"""
        from app import create_app
        app = create_app({'TESTING': True})

        # 테스트용 임시 라우트 추가
        @app.route('/test-middleware')
        def _test_route():
            return 'ok'

        with app.test_client() as client:
            response = client.get('/test-middleware')
            assert 'X-Request-ID' in response.headers, \
                "응답에 X-Request-ID 헤더가 없습니다"

    def test_request_id_is_uuid_format(self):
        """X-Request-ID가 UUID 형식이어야 함"""
        import re
        from app import create_app
        app = create_app({'TESTING': True})

        @app.route('/test-uuid')
        def _test_route():
            return 'ok'

        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        )

        with app.test_client() as client:
            response = client.get('/test-uuid')
            request_id = response.headers.get('X-Request-ID', '')
            assert uuid_pattern.match(request_id), \
                f"X-Request-ID가 UUID 형식이 아닙니다: {request_id}"
