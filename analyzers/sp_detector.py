"""
정규식 기반 C# SP 호출 패턴 탐지 모듈 — [M1.F6]
"""
import logging
import os
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

# SP 탐지 정규식 패턴 — [M1.AC 6.1]
# SqlCommand/CommandText/Dapper Execute·Query 4가지 패턴
SP_PATTERNS = [
    re.compile(r'new\s+SqlCommand\s*\(\s*"([\w_]+)"'),
    re.compile(r'\.CommandText\s*=\s*"([\w_]+)"'),
    re.compile(r'\.Execute\w*\s*\(\s*"([\w_]+)"'),
    re.compile(r'\.Query\w*\s*\(\s*"([\w_]+)"'),
]

# 결제 도메인 SP 키워드 — [M1.AC 6.4]
PAYMENT_SP_KEYWORDS = {'payment', 'settle', 'approve', 'cancel', 'refund'}

# C# 클래스·메서드 추적 패턴
_CLASS_RE = re.compile(r'\bclass\s+(\w+)')
_METHOD_RE = re.compile(
    r'(?:public|private|protected|internal|static|override|virtual|async)'
    r'\s+[\w<>\[\]]+\s+(\w+)\s*\('
)


def classify_payment_sp(sp_name: str) -> bool:
    """SP명에 결제 도메인 키워드 포함 여부 확인 — [M1.AC 6.4]"""
    return any(kw in sp_name.lower() for kw in PAYMENT_SP_KEYWORDS)


def _scan_line(line: str) -> list:
    """한 줄에서 SP명 추출 — 모든 탐지 패턴 검색."""
    sp_names = []
    for pattern in SP_PATTERNS:
        m = pattern.search(line)
        if m:
            sp_names.append(m.group(1))
    return sp_names


def _detect_context(line: str, current_class: str, current_method: str) -> tuple:
    """라인에서 C# 클래스/메서드 컨텍스트 갱신."""
    cm = _CLASS_RE.search(line)
    if cm:
        return cm.group(1), ''
    mm = _METHOD_RE.search(line)
    if mm:
        return current_class, mm.group(1)
    return current_class, current_method


def _build_sp_call(sp_name: str, file_path: str, line_no: int,
                   class_name: str, method_name: str) -> dict:
    """SPCallInfo dict 생성."""
    return {
        'sp_name': sp_name,
        'file_path': file_path,
        'line_no': line_no,
        'class_name': class_name,
        'method_name': method_name,
        'project': os.path.basename(os.path.dirname(file_path)),
        'category': 'payment' if classify_payment_sp(sp_name) else 'normal',
    }


def _analyze_file(file_path: str) -> list:
    """단일 .cs 파일에서 SP 호출 탐지. 읽기 실패 시 경고 후 스킵."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning('sp_detector: 파일 읽기 실패 — 스킵 | path=%s | error=%s',
                       file_path, type(exc).__name__)
        return []
    results = []
    current_class, current_method = '', ''
    for line_no, line in enumerate(lines, start=1):
        current_class, current_method = _detect_context(line, current_class, current_method)
        for sp_name in _scan_line(line):
            results.append(_build_sp_call(sp_name, file_path, line_no, current_class, current_method))
    return results


def detect_sp_calls(file_paths: list) -> list:
    """
    .cs 파일 목록에서 SP 호출 패턴을 탐지하여 SPCallInfo 목록 반환 — [M1.AC 6.1]
    SPCallInfo: {sp_name, file_path, line_no, class_name, method_name, project, category}
    """
    results = []
    for file_path in file_paths:
        results.extend(_analyze_file(file_path))
    return results


def build_sp_tree(calls: list) -> dict:
    """
    SPCallInfo 목록을 SP명 기준으로 그룹화하여 트리 반환 — [M1.AC 6.2]
    반환 형태: {sp_name: [SPCallInfo, ...]}
    """
    tree: dict = defaultdict(list)
    for call in calls:
        tree[call['sp_name']].append(call)
    return dict(tree)


def get_callers_by_sp(sp_name: str, calls: list) -> list:
    """SP명으로 해당 SP를 호출하는 코드 목록 반환 — [M1.AC 6.3]"""
    return [c for c in calls if c['sp_name'] == sp_name]


def get_sp_by_file(file_path: str, calls: list) -> list:
    """파일 경로로 해당 파일의 SP 호출 목록 반환 — [M1.AC 6.3]"""
    return [c for c in calls if c['file_path'] == file_path]


def detect_dead_sp(all_sp_names: list, calls: list) -> list:
    """코드에서 호출되지 않는 SP명 목록 반환 (Dead SP 탐지)."""
    called = {c['sp_name'] for c in calls}
    return [name for name in all_sp_names if name not in called]
