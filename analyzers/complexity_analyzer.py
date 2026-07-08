"""
Lizard 기반 C# 순환복잡도(CC) 측정 및 God Class 탐지 모듈 — [M1.F2]
"""
import logging
import os
from collections import defaultdict
import lizard

logger = logging.getLogger(__name__)

PAYMENT_KEYWORDS = {'payment', 'settle', 'approve', 'cancel', 'refund'}
SECURITY_KEYWORDS = {'encrypt', 'hash', 'token', 'auth', 'secret', 'key'}

# CC 등급 임계값 — [M1.AC 2.2]
CC_LOW_MAX = 4
CC_MEDIUM_MAX = 9
CC_HIGH_MAX = 14

# God Class 탐지 기준 — [M1.AC 2.5]
GOD_CLASS_FUNCTION_COUNT = 20
GOD_CLASS_AVG_CC = 8


def classify_cc_grade(cc: int) -> str:
    """CC 숫자를 등급 문자열로 변환 — 낮음(1~4)/중간(5~9)/높음(10~14)/매우높음(15+)"""
    if cc <= CC_LOW_MAX:
        return '낮음'
    elif cc <= CC_MEDIUM_MAX:
        return '중간'
    elif cc <= CC_HIGH_MAX:
        return '높음'
    return '매우높음'


def classify_payment_file(file_path: str) -> bool:
    """파일명에 결제 도메인 키워드 포함 여부 확인 — [M1.AC 2.3]"""
    name = os.path.basename(file_path).lower()
    return any(kw in name for kw in PAYMENT_KEYWORDS)


def classify_security_code(function_name: str, code_body: str) -> bool:
    """함수명 또는 코드 본문에 보안 관련 키워드 포함 여부 확인 — [M1.AC 2.4]"""
    combined = (function_name + ' ' + code_body).lower()
    return any(kw in combined for kw in SECURITY_KEYWORDS)


def _extract_class_name(long_name: str) -> str:
    """Lizard long_name에서 클래스명 추출 — C# 네임스페이스 구분자(::) 기반"""
    # Lizard C# 파서의 long_name 포맷: 'ClassName::MethodName' — 일반 Python '.' 아닌 '::' 사용
    if '::' in long_name:
        return long_name.split('::')[0]
    return ''


def _build_function_info(func, file_path: str) -> dict:
    """Lizard FunctionInfo를 FunctionInfo dict으로 변환."""
    cc = func.cyclomatic_complexity
    return {
        'function_name': func.name,
        'class_name': _extract_class_name(func.long_name),
        'file_path': file_path,
        'project': os.path.basename(os.path.dirname(file_path)),
        'cc': cc,
        'grade': classify_cc_grade(cc),
        'line_start': func.start_line,
        'category': 'normal',
    }


def analyze_complexity(file_paths: list) -> list:
    """
    Lizard로 .cs 파일 목록 CC 측정 후 FunctionInfo 딕셔너리 목록 반환 — [M1.AC 2.1]
    인코딩 오류 파일은 경고 후 스킵, 전체 분석은 계속 진행 — [M1.EX-5]
    """
    results = []
    for file_path in file_paths:
        try:
            file_info = lizard.analyze_file(file_path)
        except Exception as exc:
            logger.warning(
                'complexity_analyzer: 파일 분석 실패 — 스킵 | path=%s | error=%s',
                file_path, type(exc).__name__
            )
            continue
        results.extend(
            _build_function_info(func, file_path)
            for func in file_info.function_list
        )
    return results


def _group_by_class(functions: list) -> dict:
    """함수 목록을 class_name 기준으로 그룹화. 클래스명 없는 함수는 제외."""
    class_functions: dict = defaultdict(list)
    for func in functions:
        class_name = func.get('class_name', '')
        if class_name:
            class_functions[class_name].append(func)
    return class_functions


def detect_god_classes(functions: list) -> list:
    """
    함수 수 ≥ 20 또는 평균 CC ≥ 8 클래스를 God Class로 탐지 — [M1.AC 2.5]
    입력: FunctionInfo 딕셔너리 목록 (class_name, cc 포함)
    """
    god_classes = []
    for class_name, funcs in _group_by_class(functions).items():
        count = len(funcs)
        avg_cc = sum(f['cc'] for f in funcs) / count if count > 0 else 0
        if count >= GOD_CLASS_FUNCTION_COUNT or avg_cc >= GOD_CLASS_AVG_CC:
            god_classes.append({
                'class_name': class_name,
                'function_count': count,
                'avg_cc': round(avg_cc, 2),
                'file_path': funcs[0].get('file_path', ''),
                'project': funcs[0].get('project', ''),
            })
    return god_classes


def aggregate_by_domain(functions: list) -> dict:
    """루트 폴더 기준 함수/CC 집계 — [M1.AC 2.6]"""
    domain_data: dict = defaultdict(
        lambda: {'function_count': 0, 'total_cc': 0, 'files': set()}
    )
    for func in functions:
        parts = func['file_path'].replace('\\', '/').split('/')
        domain = parts[0] if len(parts) > 1 else 'root'
        domain_data[domain]['function_count'] += 1
        domain_data[domain]['total_cc'] += func['cc']
        domain_data[domain]['files'].add(func['file_path'])

    result = {}
    for domain, data in domain_data.items():
        count = data['function_count']
        result[domain] = {
            'function_count': count,
            'avg_cc': round(data['total_cc'] / count, 2) if count > 0 else 0,
            'file_count': len(data['files']),
        }
    return result
