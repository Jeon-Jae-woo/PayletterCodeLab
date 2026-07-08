"""
T1 > T1.2 Design Tokens CSS 변수 정의 검증 테스트

[PR-7.2] 명세에 따른 base.html CSS 변수 블록, 토큰 매핑, CDN 금지 검증.
"""
import os
import re

# PGAnalyzer 루트 경로 (이 파일 기준 두 단계 상위)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# [PR-7.2] 필수 CSS 변수 매핑 (변수명 → 기대값)
REQUIRED_CSS_VARS = {
    "--color-primary": "#12ccc1",
    "--color-primary-hover": "#0ea5a0",
    "--color-primary-light": "#e0f9f8",
    "--color-surface": "#f4f6f8",
    "--color-bg": "#ffffff",
    "--color-text-primary": "#1a1a2e",
    "--color-text-secondary": "#64748b",
    "--color-border": "#e2e8f0",
    "--color-danger": "#ef4444",
    "--color-warning": "#f59e0b",
    "--color-success": "#22c55e",
    "--color-info": "#3b82f6",
    "--sidebar-width": "220px",
    "--content-max-width": "1440px",
    "--border-radius-card": "8px",
    "--base-unit": "8px",
}

# CDN URL 패턴 (금지)
CDN_PATTERN = re.compile(r'https?://(cdn|unpkg|jsdelivr|cdnjs|fonts\.googleapis)', re.IGNORECASE)


def _read_base_html():
    path = os.path.join(PROJECT_ROOT, "templates", "base.html")
    assert os.path.exists(path), "templates/base.html 파일이 없습니다"
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestBaseHtmlExists:
    """base.html 파일 존재 검증 [EX 시나리오]"""

    def test_base_html_file_exists(self):
        path = os.path.join(PROJECT_ROOT, "templates", "base.html")
        assert os.path.exists(path), "templates/base.html 파일이 누락되었습니다"

    def test_base_html_is_not_empty(self):
        content = _read_base_html()
        assert len(content.strip()) > 0, "base.html이 빈 파일입니다"


class TestCssVariablesBlock:
    """CSS 변수 블록 구조 검증 [Normal 시나리오]"""

    def setup_method(self):
        self._content = _read_base_html()

    def test_root_selector_exists(self):
        """:root 셀렉터 블록이 존재해야 함"""
        assert ":root" in self._content, "base.html에 :root 셀렉터가 없습니다"

    def test_style_tag_contains_root_block(self):
        """<style> 태그 내에 :root 블록이 있어야 함"""
        style_match = re.search(r'<style[^>]*>(.*?)</style>', self._content, re.DOTALL)
        assert style_match is not None, "<style> 태그가 없습니다"
        assert ":root" in style_match.group(1), "<style> 태그 내에 :root 블록이 없습니다"


class TestCssTokenMapping:
    """[PR-7.2] CSS 변수 토큰 매핑 검증 [Normal 시나리오]"""

    def setup_method(self):
        self._content = _read_base_html()

    def test_all_required_css_vars_defined(self):
        """16개 필수 CSS 변수 전체 정의 검증"""
        missing = [var for var in REQUIRED_CSS_VARS if var not in self._content]
        assert not missing, f"누락된 CSS 변수: {missing}"

    def test_color_primary_value(self):
        assert "--color-primary: #12ccc1" in self._content

    def test_color_primary_hover_value(self):
        assert "--color-primary-hover: #0ea5a0" in self._content

    def test_color_primary_light_value(self):
        assert "--color-primary-light: #e0f9f8" in self._content

    def test_color_surface_value(self):
        assert "--color-surface: #f4f6f8" in self._content

    def test_color_bg_value(self):
        assert "--color-bg: #ffffff" in self._content

    def test_color_text_primary_value(self):
        assert "--color-text-primary: #1a1a2e" in self._content

    def test_color_text_secondary_value(self):
        assert "--color-text-secondary: #64748b" in self._content

    def test_color_border_value(self):
        assert "--color-border: #e2e8f0" in self._content

    def test_color_danger_value(self):
        assert "--color-danger: #ef4444" in self._content

    def test_color_warning_value(self):
        assert "--color-warning: #f59e0b" in self._content

    def test_color_success_value(self):
        assert "--color-success: #22c55e" in self._content

    def test_color_info_value(self):
        assert "--color-info: #3b82f6" in self._content

    def test_sidebar_width_value(self):
        assert "--sidebar-width: 220px" in self._content

    def test_content_max_width_value(self):
        assert "--content-max-width: 1440px" in self._content

    def test_border_radius_card_value(self):
        assert "--border-radius-card: 8px" in self._content

    def test_base_unit_value(self):
        assert "--base-unit: 8px" in self._content


class TestFontFamily:
    """폰트 패밀리 정의 검증 [Normal 시나리오]"""

    def setup_method(self):
        self._content = _read_base_html()

    def test_malgun_gothic_font_defined(self):
        """Malgun Gothic 시스템 폰트 정의 확인"""
        assert "Malgun Gothic" in self._content, "한글 우선 폰트 'Malgun Gothic'이 정의되지 않았습니다"

    def test_apple_sd_gothic_neo_fallback(self):
        """Apple SD Gothic Neo 폴백 폰트 정의 확인"""
        assert "Apple SD Gothic Neo" in self._content, "Apple 폴백 폰트가 정의되지 않았습니다"


class TestCdnForbidden:
    """CDN URL 금지 검증 [Boundary 시나리오] — [PR-8] CDN 완전 금지"""

    def setup_method(self):
        self._content = _read_base_html()

    def test_no_cdn_urls_in_base_html(self):
        """외부 CDN URL이 base.html에 없어야 함"""
        cdn_matches = CDN_PATTERN.findall(self._content)
        assert not cdn_matches, f"CDN URL 발견 (폐쇄망 정책 위반): {cdn_matches}"

    def test_no_google_fonts_import(self):
        """Google Fonts CDN 참조 없음"""
        assert "fonts.googleapis.com" not in self._content, "Google Fonts CDN 참조가 있습니다"

    def test_tailwind_local_reference(self):
        """Tailwind CSS가 로컬 static 경로로 참조되어야 함"""
        assert "static/css/tailwind.min.css" in self._content or "tailwind.min.css" in self._content, \
            "tailwind.min.css 로컬 번들 참조가 없습니다"

    def test_tailwind_min_css_file_exists(self):
        """static/css/tailwind.min.css 플레이스홀더 파일 존재 확인"""
        path = os.path.join(PROJECT_ROOT, "static", "css", "tailwind.min.css")
        assert os.path.exists(path), "static/css/tailwind.min.css 파일이 없습니다 (플레이스홀더라도 필요)"
