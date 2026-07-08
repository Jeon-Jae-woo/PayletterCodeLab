"""
T3 > T3.5 — flow_analyzer 단위 테스트

[M1.AC 5.1] 호출 그래프 추출 / [M1.AC 5.3] CC enrichment / [M1.AC 5.4] 포커스 모드
"""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# [S-FLOW-01~07] 호출 그래프 추출 (extract_call_graph)
# ---------------------------------------------------------------------------

class TestExtractCallGraph:
    """extract_call_graph() — .cs 파일에서 클래스/호출 관계 추출 [M1.AC 5.1]"""

    def _write_cs(self, tmp_path, filename, code):
        f = tmp_path / filename
        f.write_text(code, encoding='utf-8')
        return str(f)

    def test_class_detected_as_node(self, tmp_path):
        """[M1.AC 5.1] .cs 파일의 클래스가 노드로 추출되어야 함"""
        from analyzers.flow_analyzer import extract_call_graph
        path = self._write_cs(
            tmp_path, "PaymentService.cs",
            'public class PaymentService {\n'
            '    public void Process() { }\n'
            '}\n'
        )
        graph = extract_call_graph([path])
        node_ids = [n['id'] for n in graph['nodes']]
        assert 'PaymentService' in node_ids, "PaymentService 클래스가 노드로 추출되어야 합니다"

    def test_new_instance_creates_edge(self, tmp_path):
        """[M1.AC 5.1] new ClassName() 패턴 → caller→ClassName 엣지 생성"""
        from analyzers.flow_analyzer import extract_call_graph
        path = self._write_cs(
            tmp_path, "OrderService.cs",
            'public class OrderService {\n'
            '    public void Run() {\n'
            '        var ps = new PaymentService();\n'
            '    }\n'
            '}\n'
        )
        graph = extract_call_graph([path])
        callees = [e['callee'] for e in graph['edges']]
        assert 'PaymentService' in callees, \
            "new PaymentService() → PaymentService 엣지가 생성되어야 합니다"

    def test_graph_has_required_keys(self, tmp_path):
        """CallGraphData에 nodes/edges 키가 있어야 함"""
        from analyzers.flow_analyzer import extract_call_graph
        path = self._write_cs(
            tmp_path, "Simple.cs",
            'public class Simple {\n'
            '    public void Run() { }\n'
            '}\n'
        )
        graph = extract_call_graph([path])
        assert 'nodes' in graph, "CallGraphData에 nodes 키가 있어야 합니다"
        assert 'edges' in graph, "CallGraphData에 edges 키가 있어야 합니다"

    def test_node_has_required_fields(self, tmp_path):
        """노드에 id/name/file/avg_cc/ref_count/is_payment 필드가 있어야 함"""
        from analyzers.flow_analyzer import extract_call_graph
        path = self._write_cs(
            tmp_path, "PayService.cs",
            'public class PayService {\n'
            '    public void Run() { }\n'
            '}\n'
        )
        graph = extract_call_graph([path])
        assert len(graph['nodes']) >= 1, "최소 1개 노드가 추출되어야 합니다"
        node = graph['nodes'][0]
        required = {'id', 'name', 'file', 'avg_cc', 'ref_count', 'is_payment'}
        missing = required - node.keys()
        assert not missing, f"필수 키 누락: {missing}"

    def test_payment_class_is_payment_true(self, tmp_path):
        """[M1.AC 5.1] 결제 도메인 클래스명 → is_payment=True"""
        from analyzers.flow_analyzer import extract_call_graph
        path = self._write_cs(
            tmp_path, "PaymentRepo.cs",
            'public class PaymentRepo {\n'
            '    public void Insert() { }\n'
            '}\n'
        )
        graph = extract_call_graph([path])
        pay_nodes = [n for n in graph['nodes'] if n['id'] == 'PaymentRepo']
        assert pay_nodes, "PaymentRepo 노드가 있어야 합니다"
        assert pay_nodes[0]['is_payment'] is True, \
            "payment 키워드 포함 클래스는 is_payment=True이어야 합니다"

    def test_empty_file_list_returns_empty_graph(self):
        """빈 파일 목록 → 빈 그래프"""
        from analyzers.flow_analyzer import extract_call_graph
        graph = extract_call_graph([])
        assert graph['nodes'] == [], "파일 없으면 nodes가 빈 리스트여야 합니다"
        assert graph['edges'] == [], "파일 없으면 edges가 빈 리스트여야 합니다"

    def test_unreadable_file_skipped(self, tmp_path):
        """파일 읽기 실패 시 스킵 후 빈 그래프 반환"""
        from analyzers.flow_analyzer import extract_call_graph
        nonexistent = str(tmp_path / "missing.cs")
        graph = extract_call_graph([nonexistent])
        assert isinstance(graph, dict), "읽기 실패 파일도 예외 없이 dict 반환해야 합니다"
        assert graph['nodes'] == [], "읽기 실패 파일은 빈 nodes를 반환해야 합니다"


# ---------------------------------------------------------------------------
# [S-FLOW-08~09] 포커스 서브그래프 (get_focus_subgraph)
# ---------------------------------------------------------------------------

class TestGetFocusSubgraph:
    """get_focus_subgraph() — 노드 중심 서브그래프 추출 [M1.AC 5.4]"""

    def _make_graph(self):
        return {
            'nodes': [
                {'id': 'A', 'name': 'A', 'file': 'a.cs'},
                {'id': 'B', 'name': 'B', 'file': 'b.cs'},
                {'id': 'C', 'name': 'C', 'file': 'c.cs'},
            ],
            'edges': [
                {'caller': 'A', 'callee': 'B'},
                {'caller': 'B', 'callee': 'C'},
            ],
        }

    def test_focus_includes_direct_neighbors(self):
        """[M1.AC 5.4] levels=1 포커스 → 포커스 노드 + 직접 이웃 포함"""
        from analyzers.flow_analyzer import get_focus_subgraph
        graph = self._make_graph()
        sub = get_focus_subgraph('B', graph, levels=1)
        node_ids = {n['id'] for n in sub['nodes']}
        assert 'B' in node_ids, "포커스 노드 B가 포함되어야 합니다"
        assert 'A' in node_ids, "B의 caller(A)가 포함되어야 합니다"
        assert 'C' in node_ids, "B의 callee(C)가 포함되어야 합니다"

    def test_focus_returns_valid_structure(self):
        """서브그래프 반환 형태에 nodes/edges 키 포함"""
        from analyzers.flow_analyzer import get_focus_subgraph
        graph = self._make_graph()
        sub = get_focus_subgraph('A', graph, levels=2)
        assert 'nodes' in sub, "서브그래프에 nodes 키가 있어야 합니다"
        assert 'edges' in sub, "서브그래프에 edges 키가 있어야 합니다"
        assert len(sub['nodes']) >= 1, "포커스 서브그래프에 최소 1개 노드가 있어야 합니다"


# ---------------------------------------------------------------------------
# [S-FLOW-10~11] 호출 트리 (get_call_tree)
# ---------------------------------------------------------------------------

class TestGetCallTree:
    """get_call_tree() — 깊이 제한 호출 트리 탐색 [M1.AC 5.4]"""

    def _make_graph(self):
        return {
            'nodes': [
                {'id': 'Root', 'name': 'Root'},
                {'id': 'Child', 'name': 'Child'},
                {'id': 'Grandchild', 'name': 'Grandchild'},
            ],
            'edges': [
                {'caller': 'Root', 'callee': 'Child'},
                {'caller': 'Child', 'callee': 'Grandchild'},
            ],
        }

    def test_call_tree_has_required_keys(self):
        """[M1.AC 5.4] TreeNode에 id/name/depth/children 키가 있어야 함"""
        from analyzers.flow_analyzer import get_call_tree
        graph = self._make_graph()
        tree = get_call_tree('Root', graph, depth=3)
        assert 'id' in tree, "TreeNode에 id 키가 있어야 합니다"
        assert 'children' in tree, "TreeNode에 children 키가 있어야 합니다"
        assert 'depth' in tree, "TreeNode에 depth 키가 있어야 합니다"
        assert tree['id'] == 'Root', "루트 노드 id가 Root여야 합니다"

    def test_call_tree_depth_limit(self):
        """depth=1이면 직접 자식까지만 탐색, 손자 children은 빈 리스트"""
        from analyzers.flow_analyzer import get_call_tree
        graph = self._make_graph()
        tree = get_call_tree('Root', graph, depth=1)
        assert len(tree['children']) >= 1, "depth=1에서 직접 자식이 있어야 합니다"
        for child in tree['children']:
            assert child['children'] == [], \
                "depth=1 한계에서 손자 children이 비어야 합니다"


# ---------------------------------------------------------------------------
# [S-FLOW-12~14] CC 복잡도 enrichment (enrich_with_complexity)
# ---------------------------------------------------------------------------

class TestEnrichWithComplexity:
    """enrich_with_complexity() — CC 정보 노드 보강 [M1.AC 5.3]"""

    def test_enrich_adds_avg_cc(self):
        """[M1.AC 5.3] complexity_results로 노드 avg_cc 보강"""
        from analyzers.flow_analyzer import enrich_with_complexity
        graph = {
            'nodes': [
                {'id': 'PaymentService', 'name': 'PaymentService', 'file': 'p.cs',
                 'avg_cc': 0.0, 'ref_count': 0, 'is_payment': True, 'grade': 'low'},
            ],
            'edges': [],
        }
        complexity_results = [
            {'class_name': 'PaymentService', 'function_name': 'Process',
             'cc': 8, 'grade': '중간', 'file_path': 'p.cs'},
            {'class_name': 'PaymentService', 'function_name': 'Validate',
             'cc': 4, 'grade': '낮음', 'file_path': 'p.cs'},
        ]
        enriched = enrich_with_complexity(graph, complexity_results)
        pay_nodes = [n for n in enriched['nodes'] if n['id'] == 'PaymentService']
        assert pay_nodes, "PaymentService 노드가 있어야 합니다"
        assert pay_nodes[0]['avg_cc'] == 6.0, \
            "avg_cc는 (8+4)/2=6.0이어야 합니다"

    def test_enrich_preserves_edges(self):
        """enrich_with_complexity가 edges를 그대로 유지해야 함"""
        from analyzers.flow_analyzer import enrich_with_complexity
        graph = {
            'nodes': [
                {'id': 'A', 'name': 'A', 'avg_cc': 0.0, 'ref_count': 0,
                 'is_payment': False, 'grade': 'low', 'file': 'a.cs'},
            ],
            'edges': [{'caller': 'A', 'callee': 'B'}],
        }
        enriched = enrich_with_complexity(graph, [])
        assert enriched['edges'] == [{'caller': 'A', 'callee': 'B'}], \
            "edges가 변경 없이 유지되어야 합니다"

    def test_enrich_no_complexity_preserves_original_cc(self):
        """complexity_results 없을 때 기존 avg_cc 유지"""
        from analyzers.flow_analyzer import enrich_with_complexity
        graph = {
            'nodes': [
                {'id': 'OrderService', 'name': 'OrderService', 'file': 'o.cs',
                 'avg_cc': 3.5, 'ref_count': 1, 'is_payment': False, 'grade': 'low'},
            ],
            'edges': [],
        }
        enriched = enrich_with_complexity(graph, [])
        assert enriched['nodes'][0]['avg_cc'] == 3.5, \
            "complexity_results 없으면 원래 avg_cc가 유지되어야 합니다"
