"""
T3 > T3.1 — sp_detector 단위 테스트 스켈레톤 (TDD Red Phase)

[M1.S8] SP 호출 탐지 — SqlCommand 패턴 / [M1.AC 6.1]
"""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# [S-SP-01~07] SP 호출 탐지 (detect_sp_calls)
# ---------------------------------------------------------------------------

class TestDetectSpCalls:
    """detect_sp_calls() — .cs 파일에서 SP 호출 패턴 탐지 [M1.AC 6.1]"""

    def _write_cs(self, tmp_path, filename, code):
        f = tmp_path / filename
        f.write_text(code, encoding='utf-8')
        return str(f)

    def test_sql_command_pattern_detected(self, tmp_path):
        """[M1.S8] `new SqlCommand("SP_NAME", conn)` → SP_NAME 탐지"""
        from analyzers.sp_detector import detect_sp_calls
        path = self._write_cs(
            tmp_path, "PaymentRepo.cs",
            'public class PaymentRepo {\n'
            '    public void Execute() {\n'
            '        var cmd = new SqlCommand("UP_PAYMENT_TX_INS", conn);\n'
            '    }\n'
            '}\n'
        )
        results = detect_sp_calls([path])
        sp_names = [r['sp_name'] for r in results]
        assert 'UP_PAYMENT_TX_INS' in sp_names, \
            "SqlCommand 패턴에서 SP명이 탐지되어야 합니다"

    def test_command_text_assignment_pattern_detected(self, tmp_path):
        """[M1.S8] `cmd.CommandText = "SP_NAME"` → SP_NAME 탐지"""
        from analyzers.sp_detector import detect_sp_calls
        path = self._write_cs(
            tmp_path, "OrderRepo.cs",
            'public class OrderRepo {\n'
            '    public void Execute() {\n'
            '        cmd.CommandText = "UP_ORDER_INS";\n'
            '    }\n'
            '}\n'
        )
        results = detect_sp_calls([path])
        sp_names = [r['sp_name'] for r in results]
        assert 'UP_ORDER_INS' in sp_names, \
            "CommandText 대입 패턴에서 SP명이 탐지되어야 합니다"

    def test_dapper_execute_pattern_detected(self, tmp_path):
        """[M1.S8] `.Execute("SP_NAME"` → Dapper SP 탐지"""
        from analyzers.sp_detector import detect_sp_calls
        path = self._write_cs(
            tmp_path, "SettleRepo.cs",
            'public class SettleRepo {\n'
            '    public void Run() {\n'
            '        conn.Execute("UP_SETTLE_TX_UPD", param);\n'
            '    }\n'
            '}\n'
        )
        results = detect_sp_calls([path])
        sp_names = [r['sp_name'] for r in results]
        assert 'UP_SETTLE_TX_UPD' in sp_names, \
            "Dapper Execute 패턴에서 SP명이 탐지되어야 합니다"

    def test_dapper_query_pattern_detected(self, tmp_path):
        """[M1.S8] `.Query("SP_NAME"` → Dapper Query SP 탐지"""
        from analyzers.sp_detector import detect_sp_calls
        path = self._write_cs(
            tmp_path, "RefundRepo.cs",
            'public class RefundRepo {\n'
            '    public void Get() {\n'
            '        var rows = conn.Query("UP_REFUND_SEL", param);\n'
            '    }\n'
            '}\n'
        )
        results = detect_sp_calls([path])
        sp_names = [r['sp_name'] for r in results]
        assert 'UP_REFUND_SEL' in sp_names, \
            "Dapper Query 패턴에서 SP명이 탐지되어야 합니다"

    def test_result_has_required_fields(self, tmp_path):
        """[M1.S8] SPCallInfo에 sp_name, file_path, line_no 키가 있어야 함"""
        from analyzers.sp_detector import detect_sp_calls
        path = self._write_cs(
            tmp_path, "PayRepo.cs",
            'public class Pay {\n'
            '    public void Run() {\n'
            '        var cmd = new SqlCommand("UP_PAY_INS", conn);\n'
            '    }\n'
            '}\n'
        )
        results = detect_sp_calls([path])
        assert len(results) >= 1, "최소 1개 SP 호출이 탐지되어야 합니다"
        required = {'sp_name', 'file_path', 'line_no'}
        missing = required - results[0].keys()
        assert not missing, f"필수 키 누락: {missing}"

    def test_empty_file_list_returns_empty(self):
        """빈 파일 목록 입력 시 빈 리스트 반환"""
        from analyzers.sp_detector import detect_sp_calls
        result = detect_sp_calls([])
        assert result == [], "파일이 없으면 빈 리스트를 반환해야 합니다"

    def test_file_without_sp_calls_returns_empty(self, tmp_path):
        """SP 호출 없는 파일 → 빈 탐지 결과"""
        from analyzers.sp_detector import detect_sp_calls
        path = self._write_cs(
            tmp_path, "NoSP.cs",
            'public class NoSP {\n'
            '    public int Add(int a, int b) { return a + b; }\n'
            '}\n'
        )
        results = detect_sp_calls([path])
        assert results == [], "SP 호출 없는 파일은 빈 결과를 반환해야 합니다"


# ---------------------------------------------------------------------------
# [S-SP-08] SP 트리 빌드 (build_sp_tree)
# ---------------------------------------------------------------------------

class TestBuildSpTree:
    """build_sp_tree() — SP → 파일 → 클래스 → 메서드 계층 구조 [M1.AC 6.2]"""

    def test_tree_groups_by_sp_name(self):
        """동일 SP명의 호출이 같은 트리 노드 아래 그룹화되어야 함"""
        from analyzers.sp_detector import build_sp_tree
        calls = [
            {'sp_name': 'UP_PAY_INS', 'file_path': 'A.cs',
             'class_name': 'ClassA', 'method_name': 'MethodA', 'line_no': 10},
            {'sp_name': 'UP_PAY_INS', 'file_path': 'B.cs',
             'class_name': 'ClassB', 'method_name': 'MethodB', 'line_no': 20},
        ]
        tree = build_sp_tree(calls)
        assert 'UP_PAY_INS' in tree, "SP명이 트리의 최상위 키여야 합니다"
        assert len(tree['UP_PAY_INS']) == 2, "동일 SP명 호출 2건이 모두 포함되어야 합니다"


# ---------------------------------------------------------------------------
# [S-SP-09~12] 조회·Dead SP 헬퍼 (get_callers_by_sp, get_sp_by_file, detect_dead_sp)
# ---------------------------------------------------------------------------

class TestSpHelpers:
    """get_callers_by_sp(), get_sp_by_file(), detect_dead_sp() — [M1.AC 6.3]"""

    def _make_calls(self):
        return [
            {'sp_name': 'UP_PAY_INS', 'file_path': 'Pay.cs', 'line_no': 10,
             'class_name': 'PayRepo', 'method_name': 'Insert'},
            {'sp_name': 'UP_ORDER_SEL', 'file_path': 'Order.cs', 'line_no': 20,
             'class_name': 'OrderRepo', 'method_name': 'Select'},
        ]

    def test_get_callers_by_sp_returns_matching_calls(self):
        """특정 SP명으로 호출 코드 목록 필터링"""
        from analyzers.sp_detector import get_callers_by_sp
        calls = self._make_calls()
        result = get_callers_by_sp('UP_PAY_INS', calls)
        assert len(result) == 1, "UP_PAY_INS 호출은 1건이어야 합니다"
        assert result[0]['class_name'] == 'PayRepo', "올바른 호출 코드가 반환되어야 합니다"

    def test_get_sp_by_file_returns_matching_calls(self):
        """특정 파일 경로로 SP 호출 목록 필터링"""
        from analyzers.sp_detector import get_sp_by_file
        calls = self._make_calls()
        result = get_sp_by_file('Pay.cs', calls)
        assert len(result) == 1, "Pay.cs의 SP 호출은 1건이어야 합니다"
        assert result[0]['sp_name'] == 'UP_PAY_INS', "올바른 SP명이 반환되어야 합니다"

    def test_detect_dead_sp_returns_uncalled_sp_names(self):
        """코드에 호출 없는 SP명이 Dead SP 목록에 포함되어야 함"""
        from analyzers.sp_detector import detect_dead_sp
        calls = self._make_calls()
        all_sp = ['UP_PAY_INS', 'UP_ORDER_SEL', 'UP_UNUSED_PROC']
        dead = detect_dead_sp(all_sp, calls)
        assert 'UP_UNUSED_PROC' in dead, "호출 없는 SP는 Dead SP 목록에 포함되어야 합니다"
        assert 'UP_PAY_INS' not in dead, "호출된 SP는 Dead SP 목록에서 제외되어야 합니다"

    def test_detect_sp_calls_skips_unreadable_file(self, tmp_path):
        """파일 읽기 실패 시 스킵 후 빈 리스트 반환"""
        from analyzers.sp_detector import detect_sp_calls
        nonexistent = str(tmp_path / "missing.cs")
        result = detect_sp_calls([nonexistent])
        assert isinstance(result, list), "읽기 실패 파일도 예외 없이 리스트 반환해야 합니다"
        assert result == [], "읽기 실패 파일은 빈 결과를 반환해야 합니다"
