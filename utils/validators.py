"""
입력 검증 계층 — T4 > T4.1

[PR-6] Injection Defense 구현:
- URL scheme 검증 + SSRF 내부 IP 차단 [security-standards.md §1.5]
- 로컬 경로 Path Traversal 방지 [security-standards.md §1.4]
- 검색 키워드 길이 제한 [PR-6]
- 정규식 패턴 사전 검증
- 프로젝트명 파일시스템 안전 변환
"""
import ipaddress
import os
import re
import urllib.parse


class ValidationError(ValueError):
    """입력 검증 실패 예외 — HTTP 400 응답 트리거."""


# 내부 IP 범위 — SSRF 공격 벡터 차단 (security-standards.md §1.5)
_BLOCKED_NETWORKS = [
    ipaddress.ip_network('127.0.0.0/8'),      # loopback
    ipaddress.ip_network('10.0.0.0/8'),       # RFC1918 Class A
    ipaddress.ip_network('172.16.0.0/12'),    # RFC1918 Class B
    ipaddress.ip_network('192.168.0.0/16'),   # RFC1918 Class C
    ipaddress.ip_network('169.254.0.0/16'),   # link-local (AWS metadata)
    ipaddress.ip_network('::1/128'),          # IPv6 loopback
    ipaddress.ip_network('fc00::/7'),         # IPv6 unique local
]

# 파일시스템 안전 이름 — 특수문자 제거 패턴
_UNSAFE_NAME_RE = re.compile(r'[^\w\-.]')


def _validate_url_scheme(parsed) -> None:
    """http/https scheme 외 차단 — file://, data://, ftp:// 등 악용 벡터 방어."""
    if parsed.scheme not in ('http', 'https'):
        raise ValidationError(
            f"지원되지 않는 URL scheme입니다: '{parsed.scheme}'. http 또는 https만 허용됩니다."
        )
    if not parsed.hostname:
        raise ValidationError('URL에 호스트가 없습니다.')


def _validate_not_private_ip(hostname: str) -> None:
    """SSRF 내부 IP 차단 — 내부 서비스 프록시 악용 방지 (security-standards.md §1.5)."""
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        return  # 도메인 이름 — IP 검증 불필요
    for network in _BLOCKED_NETWORKS:
        try:
            if addr in network:
                raise ValidationError(
                    f'내부 IP 주소({hostname})로의 요청은 허용되지 않습니다.'
                )
        except TypeError:
            pass  # IPv4↔IPv6 혼합 비교 타입 불일치 — 무시


def validate_url(url: str) -> str:
    """URL scheme 검증 + SSRF 내부 IP 범위 차단 (security-standards.md §1.5)."""
    if not url or not url.strip():
        raise ValidationError('URL이 필요합니다.')
    parsed = urllib.parse.urlparse(url.strip())
    _validate_url_scheme(parsed)
    _validate_not_private_ip(parsed.hostname)
    return url.strip()


def _check_path_within_base(abs_path: str, abs_base: str, original: str) -> None:
    """Path Traversal 방지 — 허용 기준 경로 외부 접근 차단 (security-standards.md §1.4)."""
    if not abs_path.startswith(abs_base + os.sep) and abs_path != abs_base:
        raise ValidationError(
            f'허용되지 않는 경로입니다. 기준 경로 외부에 접근할 수 없습니다: {original}'
        )


def validate_local_path(path: str, base_allowed: str = '') -> str:
    """로컬 경로 정규화 + Path Traversal 방지 + 존재 확인 (security-standards.md §1.4)."""
    if not path or not path.strip():
        raise ValidationError('경로가 필요합니다.')
    raw_path = path.strip()
    if '\x00' in raw_path:
        # null byte 차단 — null byte injection 방어
        raise ValidationError('경로에 허용되지 않는 문자가 포함되어 있습니다.')
    abs_path = os.path.abspath(raw_path)
    if base_allowed:
        _check_path_within_base(abs_path, os.path.abspath(base_allowed), path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f'경로를 찾을 수 없습니다: {path}')
    if not os.path.isdir(abs_path):
        raise ValidationError(f'경로가 디렉터리가 아닙니다: {path}')
    return abs_path


def validate_search_keyword(keyword: str) -> str:
    """
    검색 키워드 길이 및 기본 형식 검증.

    # 길이 제한 200자 [PR-6] — 과도한 입력으로 인한 성능 저하 방어
    """
    if not keyword or not keyword.strip():
        raise ValidationError('검색 키워드가 필요합니다.')

    stripped = keyword.strip()

    if len(stripped) > 200:
        raise ValidationError(
            f'검색 키워드는 200자를 초과할 수 없습니다. (현재: {len(stripped)}자)'
        )

    return stripped


def validate_regex_pattern(pattern: str) -> str:
    """
    정규식 패턴 사전 검증 — 컴파일 실패 시 ValidationError.

    # re.compile() 시도 후 re.error → ValidationError 변환
    # 잘못된 정규식이 검색 레이어까지 전달되지 않도록 조기 차단
    """
    if not pattern or not pattern.strip():
        raise ValidationError('정규식 패턴이 필요합니다.')

    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValidationError(f'유효하지 않은 정규식 패턴입니다: {exc}') from exc

    return pattern


def sanitize_project_name(name: str) -> str:
    """
    프로젝트명을 파일시스템 안전 이름으로 변환.

    특수문자(/ \\ : * ? " < > |)를 _로 치환하여 경로 안전성 확보.
    """
    if not name or not name.strip():
        raise ValidationError('프로젝트명이 필요합니다.')

    sanitized = _UNSAFE_NAME_RE.sub('_', name.strip())

    # 길이 제한: 파일시스템 최대 이름 길이 보호
    return sanitized[:100]
