"""
HTTP 응답 헬퍼 — 공통 에러 응답 형식 통일 [PR-5]
"""
import logging

from flask import g, jsonify

logger = logging.getLogger(__name__)

# 500+ 에러 시 클라이언트에 반환하는 안전한 일반 메시지
_SERVER_ERROR_MSG = '서버 내부 오류가 발생했습니다.'


def error_response(user_message: str, status_code: int, exc: Exception = None) -> tuple:
    """구조화된 에러 응답 생성.

    [security-standards.md §8.1] — 스택 트레이스 없이 안전한 메시지만 클라이언트에 반환.
    예외 상세는 서버 로그(request_id 포함)에만 기록하여 노출 없이 추적 가능.
    """
    request_id = getattr(g, 'request_id', '')
    if exc is not None:
        # 예외 유형 및 request_id 구조화 로그 — 디버그 추적용 (클라이언트 노출 없음) [PR-5]
        logger.error(
            '라우트 예외: status=%d | type=%s',
            status_code,
            type(exc).__name__,
            extra={'context': {'request_id': request_id, 'error_type': type(exc).__name__}},
        )
    # 500+ 내부 오류는 일반 메시지로 대체 — 구현 상세 노출 방지 [security-standards.md §8.1]
    safe_message = _SERVER_ERROR_MSG if status_code >= 500 else user_message
    return jsonify({'error': safe_message, 'request_id': request_id}), status_code
