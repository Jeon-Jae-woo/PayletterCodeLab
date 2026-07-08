"""
T1 > T1.1 프로젝트 구조 초기화 검증 테스트

[PR-4] 명세에 따른 디렉터리 구조, 설정 파일 존재 여부 및 내용 검증.
"""
import os

# PGAnalyzer 루트 경로 (이 파일 기준 두 단계 상위)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# ────────────────────────────────────────────
# T1.1-N-01 : requirements.txt 패키지 포함 여부
# ────────────────────────────────────────────
class TestRequirementsTxt:
    def setup_method(self):
        path = os.path.join(PROJECT_ROOT, "requirements.txt")
        assert os.path.exists(path), "requirements.txt 파일이 없습니다"
        with open(path, encoding="utf-8") as f:
            self._content = f.read()

    def test_flask_included(self):
        assert "Flask" in self._content

    def test_lizard_included(self):
        assert "lizard" in self._content.lower()

    def test_python_gitlab_included(self):
        assert "python-gitlab" in self._content

    def test_pygithub_included(self):
        assert "PyGithub" in self._content

    def test_openpyxl_included(self):
        assert "openpyxl" in self._content

    def test_pyinstaller_included(self):
        assert "PyInstaller" in self._content

    def test_pytest_included(self):
        assert "pytest" in self._content

    def test_pytest_cov_included(self):
        assert "pytest-cov" in self._content


# ────────────────────────────────────────────
# T1.1-N-02 : pytest.ini 커버리지 설정
# ────────────────────────────────────────────
class TestPytestIni:
    def setup_method(self):
        path = os.path.join(PROJECT_ROOT, "pytest.ini")
        assert os.path.exists(path), "pytest.ini 파일이 없습니다"
        with open(path, encoding="utf-8") as f:
            self._content = f.read()

    def test_lcov_report_configured(self):
        assert "--cov-report=lcov" in self._content

    def test_json_report_configured(self):
        assert "--cov-report=json" in self._content

    def test_coverage_output_path(self):
        # lcov 출력 경로가 coverage/ 아래에 설정돼야 함
        assert "coverage/" in self._content or "./coverage/" in self._content

    def test_cov_source_targets(self):
        # analyzers/, services/ 대상 커버리지 측정
        assert "--cov=analyzers" in self._content or "cov=analyzers" in self._content


# ────────────────────────────────────────────
# T1.1-N-03 : [PR-4] 디렉터리 구조 존재 여부
# ────────────────────────────────────────────
REQUIRED_DIRS = [
    "routes",
    "services",
    "analyzers",
    "templates",
    "templates/macros",
    "static/js",
    "static/css",
    "tests/unit",
    "tests/integration",
]

REQUIRED_INITS = [
    "routes/__init__.py",
    "services/__init__.py",
    "analyzers/__init__.py",
    "tests/__init__.py",
    "tests/unit/__init__.py",
    "tests/integration/__init__.py",
]


class TestDirectoryStructure:
    def test_required_directories_exist(self):
        missing = [
            d for d in REQUIRED_DIRS
            if not os.path.isdir(os.path.join(PROJECT_ROOT, d))
        ]
        assert not missing, f"누락된 디렉터리: {missing}"

    def test_init_files_exist(self):
        missing = [
            f for f in REQUIRED_INITS
            if not os.path.exists(os.path.join(PROJECT_ROOT, f))
        ]
        assert not missing, f"누락된 __init__.py: {missing}"


# ────────────────────────────────────────────
# T1.1-B-01 : payletterCodeLab.spec add-data 지시문
# ────────────────────────────────────────────
class TestPGAnalyzerSpec:
    def _read_spec(self) -> str:
        path = os.path.join(PROJECT_ROOT, "payletterCodeLab.spec")
        assert os.path.exists(path), "payletterCodeLab.spec 파일이 없습니다"
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_templates_add_data(self):
        # [M1.EX-9] 번들 파일 누락 방지 — templates 포함 필수
        assert "templates" in self._read_spec()

    def test_static_add_data(self):
        # [M1.EX-9] 번들 파일 누락 방지 — static 포함 필수
        assert "static" in self._read_spec()

    def test_onefile_flag(self):
        assert "onefile" in self._read_spec().lower() or "COLLECT" in self._read_spec()

    def test_noconsole_flag(self):
        assert "console=False" in self._read_spec() or "noconsole" in self._read_spec().lower()


# ────────────────────────────────────────────
# T1.1-B-02 : pytest.integration.ini 설정
# ────────────────────────────────────────────
class TestIntegrationIni:
    def _read_ini(self) -> str:
        path = os.path.join(PROJECT_ROOT, "pytest.integration.ini")
        assert os.path.exists(path), "pytest.integration.ini 파일이 없습니다"
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_testpaths_set_to_integration(self):
        assert "tests/integration" in self._read_ini()


# ────────────────────────────────────────────
# T1.1-E-01 : .gitignore 제외 패턴
# ────────────────────────────────────────────
class TestGitignore:
    def _read_gitignore(self) -> str:
        path = os.path.join(PROJECT_ROOT, ".gitignore")
        assert os.path.exists(path), ".gitignore 파일이 없습니다"
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_temp_ignored(self):
        assert "temp/" in self._read_gitignore()

    def test_dist_ignored(self):
        assert "dist/" in self._read_gitignore()

    def test_coverage_ignored(self):
        assert "coverage/" in self._read_gitignore()

    def test_pycache_ignored(self):
        assert "__pycache__/" in self._read_gitignore()
