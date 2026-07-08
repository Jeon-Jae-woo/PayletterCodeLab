"""
T3 > T3.1 — dependency_analyzer 단위 테스트 스켈레톤 (TDD Red Phase)

[M1.S7] .csproj 의존성 파싱 성공 / [M1.AC 4.1]
"""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# [S-DEP-01~04] .csproj 파싱 (parse_csproj)
# ---------------------------------------------------------------------------

class TestParseCsproj:
    """parse_csproj() — .csproj XML에서 ProjectReference 추출 [M1.AC 4.1]"""

    def test_parse_project_reference(self, tmp_path):
        """[M1.S7] ProjectReference 포함 .csproj → 의존성 엣지 추출"""
        from analyzers.dependency_analyzer import parse_csproj
        csproj = tmp_path / "PaymentService.csproj"
        csproj.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<Project Sdk="Microsoft.NET.Sdk">\n'
            '  <ItemGroup>\n'
            '    <ProjectReference Include="..\\Common\\Common.csproj" />\n'
            '    <ProjectReference Include="..\\Data\\Data.csproj" />\n'
            '  </ItemGroup>\n'
            '</Project>\n',
            encoding='utf-8'
        )
        result = parse_csproj(str(csproj))
        assert 'dependencies' in result, "결과에 dependencies 키가 있어야 합니다"
        dep_names = [os.path.basename(d) for d in result['dependencies']]
        assert 'Common.csproj' in dep_names, "Common.csproj 의존성이 추출되어야 합니다"
        assert 'Data.csproj' in dep_names, "Data.csproj 의존성이 추출되어야 합니다"

    def test_parse_package_reference(self, tmp_path):
        """PackageReference도 결과에 포함되어야 함"""
        from analyzers.dependency_analyzer import parse_csproj
        csproj = tmp_path / "Api.csproj"
        csproj.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<Project Sdk="Microsoft.NET.Sdk.Web">\n'
            '  <ItemGroup>\n'
            '    <PackageReference Include="Newtonsoft.Json" Version="13.0.1" />\n'
            '  </ItemGroup>\n'
            '</Project>\n',
            encoding='utf-8'
        )
        result = parse_csproj(str(csproj))
        assert 'packages' in result, "결과에 packages 키가 있어야 합니다"
        assert 'Newtonsoft.Json' in result['packages'], \
            "PackageReference가 결과에 포함되어야 합니다"

    def test_parse_empty_csproj(self, tmp_path):
        """의존성 없는 .csproj → dependencies 빈 리스트"""
        from analyzers.dependency_analyzer import parse_csproj
        csproj = tmp_path / "Standalone.csproj"
        csproj.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<Project Sdk="Microsoft.NET.Sdk">\n'
            '</Project>\n',
            encoding='utf-8'
        )
        result = parse_csproj(str(csproj))
        assert result['dependencies'] == [], "의존성 없는 프로젝트는 빈 리스트여야 합니다"

    def test_invalid_xml_returns_error_marker(self, tmp_path):
        """[M1.EX-7] 비표준 XML → 파싱 오류 표시, 예외 없이 반환"""
        from analyzers.dependency_analyzer import parse_csproj
        csproj = tmp_path / "Broken.csproj"
        csproj.write_text('<not valid xml <<>>', encoding='utf-8')
        result = parse_csproj(str(csproj))
        assert result.get('error') is not None, \
            "비표준 XML 파싱 오류 시 error 키가 포함되어야 합니다"


# ---------------------------------------------------------------------------
# [S-DEP-05~08] 의존성 그래프 빌드 (build_dependency_graph)
# ---------------------------------------------------------------------------

class TestBuildDependencyGraph:
    """build_dependency_graph() — 프로젝트 목록 → GraphData [M1.AC 4.1]"""

    def test_graph_has_nodes_and_edges(self):
        """[M1.S7] 의존성 있는 프로젝트 목록 → nodes/edges 포함 GraphData"""
        from analyzers.dependency_analyzer import build_dependency_graph
        projects = [
            {'name': 'PaymentService', 'dependencies': ['Common']},
            {'name': 'Common', 'dependencies': []},
        ]
        graph = build_dependency_graph(projects)
        assert 'nodes' in graph, "GraphData에 nodes 키가 있어야 합니다"
        assert 'edges' in graph, "GraphData에 edges 키가 있어야 합니다"
        assert len(graph['nodes']) == 2, "노드 수는 프로젝트 수와 일치해야 합니다"
        assert len(graph['edges']) >= 1, "의존성 엣지가 1개 이상 있어야 합니다"

    def test_circular_dependency_detected(self):
        """[M1.AC 4.3] A→B→C→A 순환 의존성 탐지"""
        from analyzers.dependency_analyzer import detect_circular_dependencies
        graph = {
            'nodes': [
                {'id': 'A'}, {'id': 'B'}, {'id': 'C'},
            ],
            'edges': [
                {'source': 'A', 'target': 'B'},
                {'source': 'B', 'target': 'C'},
                {'source': 'C', 'target': 'A'},
            ],
        }
        cycles = detect_circular_dependencies(graph)
        assert len(cycles) > 0, "A→B→C→A 순환 의존성이 탐지되어야 합니다"

    def test_no_circular_dependency_returns_empty(self):
        """순환 없는 그래프 → 빈 사이클 목록"""
        from analyzers.dependency_analyzer import detect_circular_dependencies
        graph = {
            'nodes': [{'id': 'A'}, {'id': 'B'}],
            'edges': [{'source': 'A', 'target': 'B'}],
        }
        cycles = detect_circular_dependencies(graph)
        assert cycles == [], "순환 없는 그래프는 빈 리스트를 반환해야 합니다"

    def test_empty_projects_returns_empty_graph(self):
        """빈 프로젝트 목록 → 빈 그래프"""
        from analyzers.dependency_analyzer import build_dependency_graph
        graph = build_dependency_graph([])
        assert graph['nodes'] == [], "프로젝트 없으면 nodes가 빈 리스트여야 합니다"
        assert graph['edges'] == [], "프로젝트 없으면 edges가 빈 리스트여야 합니다"


# ---------------------------------------------------------------------------
# [S-DEP-09~11] 깊이 계산 및 포커스 서브그래프 (calculate_depth, get_focus_subgraph)
# ---------------------------------------------------------------------------

class TestDepthAndFocus:
    """calculate_depth(), get_focus_subgraph() — [M1.AC 4.4], [M1.AC 4.5]"""

    def _make_graph(self):
        return {
            'nodes': [{'id': 'A'}, {'id': 'B'}, {'id': 'C'}, {'id': 'D'}],
            'edges': [
                {'source': 'A', 'target': 'B', 'type': 'project'},
                {'source': 'B', 'target': 'C', 'type': 'project'},
                {'source': 'A', 'target': 'D', 'type': 'project'},
            ],
        }

    def test_calculate_depth_from_root(self):
        """루트 노드에서 각 노드까지 BFS 깊이 계산"""
        from analyzers.dependency_analyzer import calculate_depth
        graph = self._make_graph()
        depths = calculate_depth(graph, 'A')
        assert depths['A'] == 0, "루트 노드 깊이는 0이어야 합니다"
        assert depths['B'] == 1, "A→B 깊이는 1이어야 합니다"
        assert depths['C'] == 2, "A→B→C 깊이는 2이어야 합니다"
        assert depths['D'] == 1, "A→D 깊이는 1이어야 합니다"

    def test_calculate_depth_unreachable_node_excluded(self):
        """루트에서 도달 불가한 노드는 결과에 포함되지 않아야 함"""
        from analyzers.dependency_analyzer import calculate_depth
        graph = {
            'nodes': [{'id': 'X'}, {'id': 'Y'}],
            'edges': [],
        }
        depths = calculate_depth(graph, 'X')
        assert 'X' in depths, "루트 노드는 깊이 0으로 포함되어야 합니다"
        assert 'Y' not in depths, "도달 불가 노드는 결과에 없어야 합니다"

    def test_get_focus_subgraph_depth_1(self):
        """포커스 노드 B 기준 depth=1 서브그래프"""
        from analyzers.dependency_analyzer import get_focus_subgraph
        graph = self._make_graph()
        sub = get_focus_subgraph('B', graph, depth=1)
        node_ids = {n['id'] for n in sub['nodes']}
        assert 'B' in node_ids, "포커스 노드 B가 서브그래프에 포함되어야 합니다"
        assert 'A' in node_ids, "B의 역방향 의존(A)이 포함되어야 합니다"
        assert 'C' in node_ids, "B→C 방향 의존이 포함되어야 합니다"

    def test_get_focus_subgraph_returns_valid_structure(self):
        """서브그래프 반환 형태에 nodes/edges 키 포함"""
        from analyzers.dependency_analyzer import get_focus_subgraph
        graph = self._make_graph()
        sub = get_focus_subgraph('A', graph, depth=1)
        assert 'nodes' in sub, "서브그래프에 nodes 키가 있어야 합니다"
        assert 'edges' in sub, "서브그래프에 edges 키가 있어야 합니다"
