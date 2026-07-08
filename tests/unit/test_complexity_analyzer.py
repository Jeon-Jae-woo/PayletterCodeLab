"""
T3 > T3.1 — complexity_analyzer 단위 테스트 스켈레톤 (TDD Red Phase)

[M1.S4]  Lizard CC 정확 측정 / [M1.AC 2.1]
[M1.S5]  God Class 탐지 — 함수 수 기준 충족 / [M1.AC 2.5]
[M1.S11] CC 등급 경계값 — CC=4 (낮음/중간 경계) / [M1.F2]
[M1.S12] CC 등급 경계값 — CC=5 (중간 시작) / [M1.F2]
[M1.S13] CC 등급 경계값 — CC=15 (매우높음 시작) / [M1.F2]
[M1.S14] God Class 경계값 — 함수 수 20개 정확히 / [M1.AC 2.5]
"""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# [S-CX-01~05] CC 등급 분류 (classify_cc_grade)
# ---------------------------------------------------------------------------

class TestClassifyCcGrade:
    """classify_cc_grade() — CC 숫자를 등급 문자열로 변환 [M1.F2]"""

    def test_cc_4_is_low(self):
        """[M1.S11] CC=4 → '낮음' (낮음/중간 경계값 하한)"""
        from analyzers.complexity_analyzer import classify_cc_grade
        assert classify_cc_grade(4) == '낮음', "CC=4는 '낮음' 등급이어야 합니다"

    def test_cc_5_is_medium(self):
        """[M1.S12] CC=5 → '중간' (중간 등급 시작 경계)"""
        from analyzers.complexity_analyzer import classify_cc_grade
        assert classify_cc_grade(5) == '중간', "CC=5는 '중간' 등급이어야 합니다"

    def test_cc_9_is_medium(self):
        """CC=9 → '중간' (중간 등급 최대값)"""
        from analyzers.complexity_analyzer import classify_cc_grade
        assert classify_cc_grade(9) == '중간', "CC=9는 '중간' 등급이어야 합니다"

    def test_cc_10_is_high(self):
        """CC=10 → '높음' (높음 등급 시작)"""
        from analyzers.complexity_analyzer import classify_cc_grade
        assert classify_cc_grade(10) == '높음', "CC=10은 '높음' 등급이어야 합니다"

    def test_cc_15_is_very_high(self):
        """[M1.S13] CC=15 → '매우높음' (매우높음 시작 경계)"""
        from analyzers.complexity_analyzer import classify_cc_grade
        assert classify_cc_grade(15) == '매우높음', "CC=15는 '매우높음' 등급이어야 합니다"

    def test_cc_1_is_low(self):
        """CC=1 (최솟값) → '낮음'"""
        from analyzers.complexity_analyzer import classify_cc_grade
        assert classify_cc_grade(1) == '낮음', "CC=1은 '낮음' 등급이어야 합니다"


# ---------------------------------------------------------------------------
# [S-CX-06~09] Lizard CC 측정 (analyze_complexity)
# ---------------------------------------------------------------------------

class TestAnalyzeComplexity:
    """analyze_complexity() — Lizard로 .cs 파일 CC 측정 [M1.AC 2.1]"""

    def test_returns_list(self, tmp_path):
        """[M1.S4] 분석 결과가 리스트 형태로 반환되어야 함"""
        from analyzers.complexity_analyzer import analyze_complexity
        cs_file = tmp_path / "Sample.cs"
        cs_file.write_text(
            "public class Sample {\n"
            "    public void SimpleMethod() { System.Console.WriteLine(\"x\"); }\n"
            "}\n",
            encoding='utf-8'
        )
        result = analyze_complexity([str(cs_file)])
        assert isinstance(result, list), "분석 결과는 list여야 합니다"

    def test_result_has_required_fields(self, tmp_path):
        """[M1.S4] FunctionInfo에 function_name, file_path, cc, grade 키가 있어야 함"""
        from analyzers.complexity_analyzer import analyze_complexity
        cs_file = tmp_path / "Calc.cs"
        cs_file.write_text(
            "public class Calc {\n"
            "    public int Add(int a, int b) { return a + b; }\n"
            "}\n",
            encoding='utf-8'
        )
        result = analyze_complexity([str(cs_file)])
        assert len(result) >= 1, "최소 1개 함수 정보가 반환되어야 합니다"
        required = {'function_name', 'file_path', 'cc', 'grade'}
        missing = required - result[0].keys()
        assert not missing, f"필수 키 누락: {missing}"

    def test_cc_value_of_simple_method(self, tmp_path):
        """[M1.S4] 분기 없는 메서드는 CC=1이어야 함"""
        from analyzers.complexity_analyzer import analyze_complexity
        cs_file = tmp_path / "NoBranch.cs"
        cs_file.write_text(
            "public class NoBranch {\n"
            "    public void Run(string s) { System.Console.WriteLine(s); }\n"
            "}\n",
            encoding='utf-8'
        )
        result = analyze_complexity([str(cs_file)])
        assert any(f['cc'] == 1 for f in result), "분기 없는 메서드는 CC=1이어야 합니다"

    def test_empty_file_list_returns_empty(self):
        """빈 파일 목록 입력 시 빈 리스트 반환"""
        from analyzers.complexity_analyzer import analyze_complexity
        result = analyze_complexity([])
        assert result == [], "파일이 없으면 빈 리스트를 반환해야 합니다"

    def test_encoding_fallback_skips_unreadable_file(self, tmp_path):
        """[M1.S22] EUC-KR 파일 → 스킵 후 경고 기록, 전체 분석 계속"""
        from analyzers.complexity_analyzer import analyze_complexity
        # EUC-KR 인코딩으로 파일 생성 (UTF-8 디코딩 실패)
        euckr_file = tmp_path / "Korean.cs"
        euckr_file.write_bytes("// 한글주석\npublic class A {}".encode('euc-kr'))
        # 예외 없이 결과 반환, 경고 dict 포함 여부 확인
        result = analyze_complexity([str(euckr_file)])
        assert isinstance(result, list), "인코딩 오류 파일도 예외 없이 리스트 반환해야 합니다"


# ---------------------------------------------------------------------------
# [S-CX-10~14] God Class 탐지 (detect_god_classes)
# ---------------------------------------------------------------------------

class TestDetectGodClasses:
    """detect_god_classes() — 함수 수 ≥ 20 또는 평균 CC ≥ 8 클래스 탐지 [M1.AC 2.5]"""

    def _make_functions(self, class_name, count, cc=5):
        return [
            {
                'class_name': class_name,
                'function_name': f'Method{i}',
                'cc': cc,
                'file_path': 'Test.cs',
                'project': 'Proj',
            }
            for i in range(count)
        ]

    def test_class_with_21_functions_is_god_class(self):
        """[M1.S5] 함수 21개, 평균 CC=5 → God Class 목록에 포함"""
        from analyzers.complexity_analyzer import detect_god_classes
        functions = self._make_functions('PaymentService', 21, cc=5)
        result = detect_god_classes(functions)
        names = [g['class_name'] for g in result]
        assert 'PaymentService' in names, "함수 21개 클래스는 God Class로 탐지되어야 합니다"

    def test_class_with_exactly_20_functions_is_god_class(self):
        """[M1.S14] 함수 수 정확히 20개 → God Class 경계값 포함"""
        from analyzers.complexity_analyzer import detect_god_classes
        functions = self._make_functions('BorderClass', 20, cc=5)
        result = detect_god_classes(functions)
        names = [g['class_name'] for g in result]
        assert 'BorderClass' in names, "함수 수 20개(이상 조건)는 God Class에 포함되어야 합니다"

    def test_class_with_19_functions_and_low_cc_is_not_god_class(self):
        """함수 19개, 평균 CC=5 → 함수 수 기준 미달, God Class 아님"""
        from analyzers.complexity_analyzer import detect_god_classes
        functions = self._make_functions('SmallService', 19, cc=5)
        result = detect_god_classes(functions)
        names = [g['class_name'] for g in result]
        assert 'SmallService' not in names, "함수 19개, CC=5 클래스는 God Class가 아니어야 합니다"

    def test_class_with_high_avg_cc_is_god_class(self):
        """평균 CC ≥ 8 기준으로 God Class 탐지 (함수 수 무관)"""
        from analyzers.complexity_analyzer import detect_god_classes
        functions = self._make_functions('ComplexService', 5, cc=10)
        result = detect_god_classes(functions)
        names = [g['class_name'] for g in result]
        assert 'ComplexService' in names, "평균 CC=10 클래스는 God Class로 탐지되어야 합니다"

    def test_empty_input_returns_empty(self):
        """빈 함수 목록 → 빈 God Class 목록"""
        from analyzers.complexity_analyzer import detect_god_classes
        result = detect_god_classes([])
        assert result == [], "함수 목록이 비어 있으면 빈 리스트를 반환해야 합니다"


# ---------------------------------------------------------------------------
# [S-CX-15~17] 도메인/보안 분류 & 집계 헬퍼
# ---------------------------------------------------------------------------

class TestClassifyHelpers:
    """classify_payment_file(), classify_security_code() — [M1.AC 2.3], [M1.AC 2.4]"""

    def test_payment_file_detected_by_keyword(self):
        """파일명에 'Payment' 포함 → True"""
        from analyzers.complexity_analyzer import classify_payment_file
        assert classify_payment_file('PaymentRepo.cs') is True

    def test_non_payment_file_returns_false(self):
        """결제 키워드 없는 파일명 → False"""
        from analyzers.complexity_analyzer import classify_payment_file
        assert classify_payment_file('UserService.cs') is False

    def test_security_code_detected_by_function_name(self):
        """함수명에 'Encrypt' 포함 → True"""
        from analyzers.complexity_analyzer import classify_security_code
        assert classify_security_code('EncryptData', '') is True

    def test_non_security_code_returns_false(self):
        """함수명·본문 모두 보안 키워드 없음 → False"""
        from analyzers.complexity_analyzer import classify_security_code
        assert classify_security_code('CalculateTax', 'return amount * rate;') is False


class TestAggregateDomain:
    """aggregate_by_domain() — 루트 폴더 기준 집계 [M1.AC 2.6]"""

    def test_aggregate_groups_by_root_folder(self):
        """동일 루트 폴더의 함수들이 하나의 도메인으로 집계되어야 함"""
        from analyzers.complexity_analyzer import aggregate_by_domain
        functions = [
            {'file_path': 'Payment/PayRepo.cs', 'cc': 4, 'class_name': 'A'},
            {'file_path': 'Payment/SettleRepo.cs', 'cc': 6, 'class_name': 'B'},
        ]
        result = aggregate_by_domain(functions)
        assert 'Payment' in result, "루트 폴더 'Payment'가 도메인 키로 존재해야 합니다"
        assert result['Payment']['function_count'] == 2
        assert result['Payment']['avg_cc'] == 5.0


class TestAnalyzeComplexityException:
    """analyze_complexity() 예외 처리 — 파일 분석 실패 시 스킵 [M1.EX-5]"""

    def test_lizard_exception_is_caught_and_skipped(self, tmp_path):
        """Lizard 분석 오류 발생 시 해당 파일 스킵, 리스트 반환"""
        from unittest import mock
        from analyzers.complexity_analyzer import analyze_complexity
        cs_file = tmp_path / "Broken.cs"
        cs_file.write_text("public class X {}", encoding='utf-8')
        with mock.patch(
            'analyzers.complexity_analyzer.lizard.analyze_file',
            side_effect=Exception('parse error')
        ):
            result = analyze_complexity([str(cs_file)])
        assert result == [], "분석 오류 파일은 스킵되어 빈 리스트가 반환되어야 합니다"
