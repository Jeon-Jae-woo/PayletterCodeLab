"""
.csproj 의존성 파싱 및 그래프 분석 모듈 — [M1.F4]
"""
import logging
import os
import xml.etree.ElementTree as ET
from collections import deque
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# DFS 색상 상수 — 순환 의존성 탐지용
_WHITE, _GRAY, _BLACK = 0, 1, 2


def _open_csproj_root(csproj_path: str) -> Tuple[Optional[ET.Element], Optional[str]]:
    """XML 파싱 후 root 반환. OSError/ParseError 시 (None, error_msg)."""
    try:
        return ET.parse(csproj_path).getroot(), None
    except (OSError, ET.ParseError) as exc:
        logger.warning('dependency_analyzer: 파일 처리 실패 — 스킵 | path=%s | error=%s',
                       csproj_path, type(exc).__name__)
        return None, str(exc)


def parse_csproj(csproj_path: str) -> dict:
    """
    .csproj XML에서 ProjectReference와 PackageReference 추출 — [M1.AC 4.1]
    파일 읽기 또는 XML 파싱 오류 시 error 키 포함 후 반환 — [M1.EX-7]
    """
    name = os.path.splitext(os.path.basename(csproj_path))[0]
    result = {'name': name, 'path': csproj_path, 'dependencies': [], 'packages': []}
    root, err = _open_csproj_root(csproj_path)
    if err is not None:
        result['error'] = err
        return result
    for ref in root.iter('ProjectReference'):
        include = ref.get('Include', '')
        if include:
            result['dependencies'].append(include.replace('\\', '/'))
    for pkg in root.iter('PackageReference'):
        pkg_name = pkg.get('Include', '')
        if pkg_name:
            result['packages'].append(pkg_name)
    return result


def build_dependency_graph(projects: list) -> dict:
    """
    프로젝트 목록에서 GraphData(nodes, edges) 생성 — [M1.AC 4.1]
    반환 형태: {nodes: [{id, name, depth}], edges: [{source, target, type}]}
    """
    if not projects:
        return {'nodes': [], 'edges': []}

    nodes = [{'id': p['name'], 'name': p['name'], 'depth': 0} for p in projects]
    edges = []
    for proj in projects:
        source = proj['name']
        for dep in proj.get('dependencies', []):
            # 경로 또는 이름 모두 처리 — basename 후 확장자 제거로 정규화
            target = os.path.splitext(os.path.basename(dep))[0]
            edges.append({'source': source, 'target': target, 'type': 'project'})

    return {'nodes': nodes, 'edges': edges}


def _dfs(node: str, adjacency: dict, colors: dict, path: list, cycles: list) -> None:
    """DFS 색상 기반 사이클 탐지 — GRAY 노드 재방문 시 사이클 기록."""
    if node not in colors:
        return
    if colors[node] == _GRAY:
        # GRAY 재방문 = 현재 탐색 경로 상의 사이클
        cycle_start = path.index(node)
        cycles.append(list(path[cycle_start:]))
        return
    if colors[node] == _BLACK:
        return
    colors[node] = _GRAY
    path.append(node)
    for neighbor in adjacency.get(node, []):
        _dfs(neighbor, adjacency, colors, path, cycles)
    path.pop()
    colors[node] = _BLACK


def detect_circular_dependencies(graph: dict) -> list:
    """
    DFS 색상 기반 순환 의존성 탐지 — [M1.AC 4.3]
    반환: 사이클 목록 (각 사이클은 노드 ID 리스트)
    """
    adjacency = {node['id']: [] for node in graph.get('nodes', [])}
    for edge in graph.get('edges', []):
        src = edge['source']
        if src in adjacency:
            adjacency[src].append(edge['target'])
    colors = {node_id: _WHITE for node_id in adjacency}
    cycles: list = []
    path: list = []
    for node_id in list(adjacency.keys()):
        if colors[node_id] == _WHITE:
            _dfs(node_id, adjacency, colors, path, cycles)
    return cycles


def calculate_depth(graph: dict, root_node: str) -> dict:
    """
    BFS로 루트 노드에서 각 노드까지의 의존성 깊이 계산 — [M1.AC 4.5]
    반환: {node_id: depth}
    """
    adjacency = {node['id']: [] for node in graph.get('nodes', [])}
    for edge in graph.get('edges', []):
        src = edge['source']
        if src in adjacency:
            adjacency[src].append(edge['target'])

    depths = {root_node: 0}
    queue = deque([root_node])
    while queue:
        current = queue.popleft()
        for neighbor in adjacency.get(current, []):
            if neighbor not in depths:
                depths[neighbor] = depths[current] + 1
                queue.append(neighbor)

    return depths


def _build_bidirectional_adjacency(graph: dict) -> tuple:
    """그래프 엣지에서 양방향 인접 리스트 구축 → (forward, backward) 튜플."""
    forward: dict = {node['id']: [] for node in graph.get('nodes', [])}
    backward: dict = {node['id']: [] for node in graph.get('nodes', [])}
    for edge in graph.get('edges', []):
        src, tgt = edge['source'], edge['target']
        if src in forward:
            forward[src].append(tgt)
        if tgt in backward:
            backward[tgt].append(src)
    return forward, backward


def get_focus_subgraph(node_id: str, graph: dict, depth: int = 1) -> dict:
    """
    특정 노드 중심으로 depth 단계 이내의 서브그래프 반환 — [M1.AC 4.4]
    양방향(의존하는 쪽 + 의존받는 쪽) BFS 탐색으로 포커스 모드 구현
    """
    forward, backward = _build_bidirectional_adjacency(graph)
    included = {node_id}
    frontier = {node_id}
    for _ in range(depth):
        next_frontier = set()
        for n in frontier:
            next_frontier.update(forward.get(n, []))
            next_frontier.update(backward.get(n, []))
        frontier = next_frontier - included
        included.update(frontier)
    nodes_map = {n['id']: n for n in graph.get('nodes', [])}
    return {
        'nodes': [nodes_map[n] for n in included if n in nodes_map],
        'edges': [e for e in graph.get('edges', [])
                  if e['source'] in included and e['target'] in included],
    }
