"""
T1 > T1.3 공통 Jinja2 레이아웃·매크로 컴포넌트 구축 검증 테스트

[PR-7.3] 컴포넌트 전략, [GR-4.1] 4-State UI, [PR-7.1] UI Tech Stack 준수 검증.
"""
import os
import re

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# 필수 네비게이션 링크 (사이드바 7개)
REQUIRED_NAV_ROUTES = [
    "setup",
    "dashboard",
    "complexity",
    "search",
    "dependency-graph",
    "flow-graph",
    "sp-flow",
]

# 4-State 매크로 이름 목록
REQUIRED_MACROS = [
    "loading_skeleton",
    "error_banner",
    "empty_state",
    "progress_bar",
]

CDN_PATTERN = re.compile(r'https?://(cdn|unpkg|jsdelivr|cdnjs|fonts\.googleapis)', re.IGNORECASE)


def _read_file(rel_path):
    path = os.path.join(PROJECT_ROOT, rel_path)
    assert os.path.exists(path), f"{rel_path} 파일이 없습니다"
    with open(path, encoding="utf-8") as f:
        return f.read()


# ─────────────────────────────────────────────
# base.html 레이아웃 검증
# ─────────────────────────────────────────────

class TestBaseHtmlLayout:
    """base.html 사이드바 + 메인 레이아웃 구조 검증 [Normal 시나리오]"""

    def setup_method(self):
        self._content = _read_file("templates/base.html")

    def test_sidebar_element_present(self):
        """사이드바 요소가 HTML에 존재해야 함"""
        assert "sidebar" in self._content, "base.html에 sidebar 요소가 없습니다"

    def test_main_content_area_present(self):
        """메인 콘텐츠 영역이 존재해야 함"""
        assert "main-content" in self._content or "{% block content %}" in self._content, \
            "base.html에 메인 콘텐츠 영역이 없습니다"

    def test_sidebar_width_var_used(self):
        """사이드바 너비로 CSS 변수 var(--sidebar-width) 사용"""
        assert "var(--sidebar-width)" in self._content or "sidebar-width" in self._content, \
            "사이드바에 --sidebar-width 토큰이 사용되지 않았습니다"

    def test_no_cdn_in_base_html(self):
        """base.html에 CDN URL 없음 [PR-8]"""
        matches = CDN_PATTERN.findall(self._content)
        assert not matches, f"CDN URL 발견 (폐쇄망 정책 위반): {matches}"


class TestBaseHtmlNavigation:
    """사이드바 네비게이션 링크 검증 [Normal 시나리오]"""

    def setup_method(self):
        self._content = _read_file("templates/base.html")

    def test_all_nav_routes_present(self):
        """7개 네비게이션 경로 모두 base.html에 존재해야 함"""
        missing = [r for r in REQUIRED_NAV_ROUTES if r not in self._content]
        assert not missing, f"누락된 네비게이션 경로: {missing}"

    def test_setup_nav_link(self):
        assert "setup" in self._content

    def test_dashboard_nav_link(self):
        assert "dashboard" in self._content

    def test_complexity_nav_link(self):
        assert "complexity" in self._content

    def test_search_nav_link(self):
        assert "search" in self._content

    def test_dependency_graph_nav_link(self):
        assert "dependency-graph" in self._content

    def test_flow_graph_nav_link(self):
        assert "flow-graph" in self._content

    def test_sp_flow_nav_link(self):
        assert "sp-flow" in self._content


class TestBaseHtmlJinja2Blocks:
    """Jinja2 블록 구조 검증 [Boundary 시나리오]"""

    def setup_method(self):
        self._content = _read_file("templates/base.html")

    def test_content_block_defined(self):
        """{% block content %} 정의"""
        assert "{% block content %}" in self._content, "content 블록이 없습니다"

    def test_title_block_defined(self):
        """{% block title %} 정의"""
        assert "{% block title %}" in self._content, "title 블록이 없습니다"

    def test_extra_scripts_block_defined(self):
        """{% block extra_scripts %} 정의 (화면별 JS 주입용)"""
        assert "{% block extra_scripts %}" in self._content, "extra_scripts 블록이 없습니다"


# ─────────────────────────────────────────────
# ui_components.html 매크로 검증
# ─────────────────────────────────────────────

class TestMacrosFileExists:
    """macros/ui_components.html 파일 존재 [EX 시나리오]"""

    def test_ui_components_file_exists(self):
        path = os.path.join(PROJECT_ROOT, "templates", "macros", "ui_components.html")
        assert os.path.exists(path), "templates/macros/ui_components.html 파일이 없습니다"

    def test_ui_components_not_empty(self):
        content = _read_file("templates/macros/ui_components.html")
        assert len(content.strip()) > 0, "ui_components.html이 빈 파일입니다"


class TestFourStateMacros:
    """4-State 매크로 4종 구현 검증 [Normal 시나리오] — [GR-4.1]"""

    def setup_method(self):
        self._content = _read_file("templates/macros/ui_components.html")

    def test_all_required_macros_defined(self):
        """4개 필수 매크로 전체 정의 확인"""
        missing = [m for m in REQUIRED_MACROS if f"macro {m}" not in self._content]
        assert not missing, f"누락된 매크로: {missing}"

    def test_loading_skeleton_macro(self):
        """loading_skeleton 매크로 정의 확인"""
        assert "macro loading_skeleton" in self._content

    def test_error_banner_macro(self):
        """error_banner 매크로 정의 확인"""
        assert "macro error_banner" in self._content

    def test_empty_state_macro(self):
        """empty_state 매크로 정의 확인"""
        assert "macro empty_state" in self._content

    def test_progress_bar_macro(self):
        """progress_bar 매크로 정의 확인"""
        assert "macro progress_bar" in self._content

    def test_no_cdn_in_macros(self):
        """매크로 파일에 CDN URL 없음 [PR-8]"""
        matches = CDN_PATTERN.findall(self._content)
        assert not matches, f"CDN URL 발견: {matches}"


class TestMacroLineLimits:
    """[GR-2.2] UI 컴포넌트 ≤ 50줄 검증 [Boundary 시나리오]"""

    def setup_method(self):
        self._content = _read_file("templates/macros/ui_components.html")

    def _get_macro_lines(self, macro_name):
        """매크로 블록의 줄 수를 추출하는 헬퍼"""
        pattern = rf'{{% macro {macro_name}[^%]*%}}(.*?){{% endmacro %}}'
        match = re.search(pattern, self._content, re.DOTALL)
        if not match:
            return 0
        return len(match.group(1).splitlines())

    def test_loading_skeleton_under_50_lines(self):
        lines = self._get_macro_lines("loading_skeleton")
        assert lines > 0, "loading_skeleton 매크로를 찾을 수 없습니다"
        assert lines <= 50, f"loading_skeleton이 {lines}줄 — [GR-2.2] 50줄 초과"

    def test_error_banner_under_50_lines(self):
        lines = self._get_macro_lines("error_banner")
        assert lines > 0, "error_banner 매크로를 찾을 수 없습니다"
        assert lines <= 50, f"error_banner가 {lines}줄 — [GR-2.2] 50줄 초과"

    def test_empty_state_under_50_lines(self):
        lines = self._get_macro_lines("empty_state")
        assert lines > 0, "empty_state 매크로를 찾을 수 없습니다"
        assert lines <= 50, f"empty_state가 {lines}줄 — [GR-2.2] 50줄 초과"

    def test_progress_bar_under_50_lines(self):
        lines = self._get_macro_lines("progress_bar")
        assert lines > 0, "progress_bar 매크로를 찾을 수 없습니다"
        assert lines <= 50, f"progress_bar가 {lines}줄 — [GR-2.2] 50줄 초과"


# ─────────────────────────────────────────────
# app.js 4-State 전환 유틸 검증
# ─────────────────────────────────────────────

class TestAppJsUtility:
    """app.js 4-State 전환 유틸 검증 [Normal 시나리오]"""

    def setup_method(self):
        self._content = _read_file("static/js/app.js")

    def test_switch_state_function_defined(self):
        """switchState(component, state) 함수 정의 확인"""
        assert "switchState" in self._content, "switchState 함수가 app.js에 없습니다"

    def test_app_js_not_empty(self):
        assert len(self._content.strip()) > 0, "app.js가 빈 파일입니다"

    def test_no_cdn_in_app_js(self):
        """app.js에 CDN URL 없음"""
        matches = CDN_PATTERN.findall(self._content)
        assert not matches, f"CDN URL 발견: {matches}"
