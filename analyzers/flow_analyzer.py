"""
C# 파일 호출 흐름 파싱 모듈 — [M1.F5]
"""
import logging
import re

logger = logging.getLogger(__name__)

# C# 구조 탐지 정규식 — 모듈 레벨 사전 컴파일
_CLASS_RE = re.compile(r'\bclass\s+(\w+)')
_NEW_INSTANCE_RE = re.compile(r'\bnew\s+(\w+)\s*\(')
# 소문자 인스턴스.대문자 메서드 패턴 — 인스턴스 메서드 호출 탐지
_INSTANCE_CALL_RE = re.compile(r'\b([a-z]\w*)\.([A-Z]\w*)\s*\(')

_PAYMENT_KEYWORDS = {'payment', 'settle', 'approve', 'cancel', 'refund'}


def _make_node(class_name: str, file_path: str) -> dict:
    """클래스명/파일 경로로 CallGraph 노드 생성."""
    return {
        'id': class_name,
        'name': class_name,
        'file': file_path,
        'avg_cc': 0.0,
        'ref_count': 0,
        'is_payment': any(kw in class_name.lower() for kw in _PAYMENT_KEYWORDS),
        'grade': 'low',
    }


def _scan_calls(line: str, current_class: str) -> list:
    """한 줄에서 new/인스턴스 호출 패턴 추출 → [(caller, callee)] 리스트."""
    if not current_class:
        return []
    calls = []
    for m in _NEW_INSTANCE_RE.finditer(line):
        callee = m.group(1)
        if callee != current_class:
            calls.append((current_class, callee))
    for m in _INSTANCE_CALL_RE.finditer(line):
        calls.append((current_class, f'{m.group(1)}.{m.group(2)}'))
    return calls


def _analyze_file(file_path: str) -> tuple:
    """단일 .cs 파일 클래스/호출 추출. 읽기 실패 시 경고 후 스킵."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning('flow_analyzer: 파일 읽기 실패 — 스킵 | path=%s | error=%s',
                       file_path, type(exc).__name__)
        return {}, []
    nodes: dict = {}
    edges: list = []
    current_class = ''
    for line in lines:
        cm = _CLASS_RE.search(line)
        if cm:
            current_class = cm.group(1)
            if current_class not in nodes:
                nodes[current_class] = _make_node(current_class, file_path)
        else:
            for caller, callee in _scan_calls(line, current_class):
                edges.append({'caller': caller, 'callee': callee})
    return nodes, edges


def extract_call_graph(file_paths: list) -> dict:
    """
    .cs 파일 목록에서 클래스 간 호출 그래프 추출 — [M1.AC 5.1]
    반환 형태: {nodes: [{id, name, file, avg_cc, ref_count, is_payment, grade}],
               edges: [{caller, callee}]}
    """
    all_nodes: dict = {}
    all_edges: list = []
    for file_path in file_paths:
        nodes, edges = _analyze_file(file_path)
        for node_id, node in nodes.items():
            if node_id in all_nodes:
                all_nodes[node_id]['ref_count'] += node['ref_count']
            else:
                all_nodes[node_id] = node
        all_edges.extend(edges)
    return {'nodes': list(all_nodes.values()), 'edges': all_edges}


def get_focus_subgraph(node_id: str, graph: dict, levels: int = 2) -> dict:
    """
    특정 노드 중심으로 levels 단계 이내의 서브그래프 반환 — [M1.AC 5.4]
    양방향(호출하는 쪽 + 호출받는 쪽) BFS로 포커스 모드 구현
    """
    forward: dict = {}
    backward: dict = {}
    for edge in graph.get('edges', []):
        forward.setdefault(edge['caller'], []).append(edge['callee'])
        backward.setdefault(edge['callee'], []).append(edge['caller'])
    included = {node_id}
    frontier = {node_id}
    for _ in range(levels):
        next_f: set = set()
        for n in frontier:
            next_f.update(forward.get(n, []))
            next_f.update(backward.get(n, []))
        frontier = next_f - included
        included.update(frontier)
    nodes_map = {n['id']: n for n in graph.get('nodes', [])}
    return {
        'nodes': [nodes_map[n] for n in included if n in nodes_map],
        'edges': [e for e in graph.get('edges', [])
                  if e['caller'] in included and e['callee'] in included],
    }


def _build_call_tree_node(
    forward: dict, node_id: str, cur_depth: int, max_depth: int, visited: set
) -> dict:
    """재귀 호출 트리 노드 구축 — 사이클 방지 visited 집합 사용."""
    node = {'id': node_id, 'name': node_id, 'depth': cur_depth, 'children': []}
    if cur_depth >= max_depth or node_id in visited:
        return node
    seen = visited | {node_id}
    for child in forward.get(node_id, []):
        node['children'].append(
            _build_call_tree_node(forward, child, cur_depth + 1, max_depth, seen)
        )
    return node


def get_call_tree(start_node: str, graph: dict, depth: int = 3) -> dict:
    """
    시작 노드에서 depth 단계 재귀 탐색하여 TreeNode 반환 — [M1.AC 5.4]
    반환: {id, name, depth, children: [TreeNode]}
    """
    forward: dict = {}
    for edge in graph.get('edges', []):
        forward.setdefault(edge['caller'], []).append(edge['callee'])
    return _build_call_tree_node(forward, start_node, 0, depth, set())


def enrich_with_complexity(graph: dict, complexity_results: list) -> dict:
    """
    CallGraphData 노드에 CC 복잡도 정보 추가 — [M1.AC 5.3]
    complexity_results: FunctionInfo 목록 (complexity_analyzer.analyze_complexity 결과)
    """
    class_cc: dict = {}
    class_grade: dict = {}
    for func in complexity_results:
        cname = func.get('class_name', '')
        if cname:
            class_cc.setdefault(cname, []).append(func.get('cc', 1))
            class_grade[cname] = func.get('grade', 'low')
    enriched = []
    for node in graph.get('nodes', []):
        n = dict(node)
        cname = n.get('name', '')
        if cname in class_cc:
            cc_list = class_cc[cname]
            n['avg_cc'] = round(sum(cc_list) / len(cc_list), 2)
            n['grade'] = class_grade.get(cname, 'low')
        enriched.append(n)
    return {'nodes': enriched, 'edges': graph.get('edges', [])}
