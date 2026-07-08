"""
구조화 로그 마스킹 필터 — T4 > T4.2

[PR-5] 마스킹 정책:
  - token, private_token, access_token, password 키 → '***'으로 대체
  - GitLab/GitHub URL Basic Auth 자격증명 → [MASKED] 치환
  - 검색 결과 스니펫 → 최대 100자 잘라서 출력

[security-standards.md §5.4] Log Sanitization
"""
import logging
import re


# Basic Auth 자격증명 패턴 — https://user:token@host 형태 탐지
# Token 메모리 보관 원칙 ([PR-6]) — 로그/파일 기록 절대 금지
_BASIC_AUTH_RE = re.compile(
    r'(https?://)([^:@\s]+:[^@\s]+@)',
    re.IGNORECASE,
)

# 민감 키워드 목록 — 이 키를 포함하는 로그 레코드 필드 마스킹
_SENSITIVE_KEYS = frozenset({'token', 'private_token', 'access_token', 'password'})

# 스니펫 최대 길이 [PR-5]
_MAX_SNIPPET_LEN = 100


def mask_url_credentials(text: str) -> str:
    """URL 내 Basic Auth 자격증명을 [MASKED]로 치환."""
    return _BASIC_AUTH_RE.sub(r'\1[MASKED]@', text)


def truncate_snippet(text: str) -> str:
    """검색 결과 스니펫을 최대 100자로 제한."""
    if len(text) > _MAX_SNIPPET_LEN:
        return text[:_MAX_SNIPPET_LEN] + '...(truncated)'
    return text


class TokenMaskingFilter(logging.Filter):
    """
    로그 레코드에서 Token 및 자격증명 노출 방지 필터.

    # Token 값이 로그에 기록되지 않도록 마스킹 — [PR-6] Secret Management 준수
    # (security-standards.md §5.4 Log Sanitization)
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # 메시지 문자열에서 URL Basic Auth 마스킹
        if record.msg and isinstance(record.msg, str):
            record.msg = mask_url_credentials(record.msg)

        # args가 dict인 경우 민감 키 마스킹
        if isinstance(record.args, dict):
            record.args = {
                k: ('***' if k.lower() in _SENSITIVE_KEYS else v)
                for k, v in record.args.items()
            }
        elif isinstance(record.args, (list, tuple)):
            # args가 위치 인수인 경우 — 민감 키 판별 불가, 문자열로 포맷 후 URL 마스킹
            try:
                formatted = record.getMessage()
                masked = mask_url_credentials(formatted)
                record.msg = masked
                record.args = ()
            except Exception:
                pass

        return True
