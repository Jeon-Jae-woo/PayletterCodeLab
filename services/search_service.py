"""
키워드/SP 전역 검색 서비스 — [M1.F3]
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_KEYWORD_LEN = 200


def _validate_keyword(keyword: str, regex_mode: bool) -> Optional[re.Pattern]:
    """키워드 유효성 검증 및 패턴 컴파일.

    Returns: 컴파일된 Pattern. 빈 키워드이면 None 반환.
    Raises: ValueError — 길이 초과 또는 유효하지 않은 정규식.
    """
    if len(keyword) > _MAX_KEYWORD_LEN:
        raise ValueError(f"키워드는 {_MAX_KEYWORD_LEN}자 이하여야 합니다")
    if not keyword:
        return None
    try:
        return re.compile(keyword if regex_mode else re.escape(keyword))
    except re.error as exc:
        raise ValueError(f"유효하지 않은 정규식: {exc}") from exc


def _search_in_content(content: str, pattern: re.Pattern) -> list:
    """파일 내용에서 패턴 일치 라인 추출 → [(line_no, snippet)] 리스트."""
    hits = []
    for line_no, line in enumerate(content.splitlines(), start=1):
        if pattern.search(line):
            hits.append((line_no, line.strip()[:200]))
    return hits


def _search_project_files(files: dict, pattern: re.Pattern) -> dict:
    """프로젝트 파일 집합 검색 → {file_path: [(line_no, snippet)]}."""
    hits = {}
    for file_path, content in files.items():
        file_hits = _search_in_content(content, pattern)
        if file_hits:
            hits[file_path] = file_hits
    return hits


def search_keyword(
    keyword: str,
    project_files: dict,
    regex_mode: bool = False,
) -> dict:
    """전체 .cs 파일에서 키워드/SP명 검색 — [M1.AC 3.1]

    Raises: ValueError — 키워드 길이 200자 초과 또는 유효하지 않은 정규식.
    Returns: {project_name: {file_path: [(line_no, snippet)]}}. 빈 키워드 → 빈 dict.
    """
    pattern = _validate_keyword(keyword, regex_mode)
    if pattern is None:
        return {}
    results = {}
    for project_name, files in project_files.items():
        project_hits = _search_project_files(files, pattern)
        if project_hits:
            results[project_name] = project_hits
    return results
