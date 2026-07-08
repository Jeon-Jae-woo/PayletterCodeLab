"""
T3 > T3.1 — search_service 단위 테스트 스켈레톤 (TDD Red Phase)

[M1.S6]  SP명 전역 검색 성공 / [M1.AC 3.1]
[M1.S15] 빈 검색어 입력 / [M1.AC 3.1]
[M1.S16] 정규식 특수문자 검색어 / [M1.AC 3.4]
[M1.S17] 대용량 검색 성능 — 500개 파일 / [M1.AC 3.6]
"""
import os
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# 공통 헬퍼
# ---------------------------------------------------------------------------

def _make_project_files(tmp_path, filemap):
    """project_files 구조 생성: {project_name: {file_path: content}}"""
    result = {}
    for proj, files in filemap.items():
        result[proj] = {}
        proj_dir = tmp_path / proj
        proj_dir.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            f = proj_dir / name
            f.write_text(content, encoding='utf-8')
            result[proj][str(f)] = content
    return result


# ---------------------------------------------------------------------------
# [S-SR-01~04] 키워드 검색 (search_keyword)
# ---------------------------------------------------------------------------

class TestSearchKeyword:
    """search_keyword() — 전체 .cs 파일 키워드/SP 검색 [M1.AC 3.1]"""

    def test_keyword_found_returns_results(self, tmp_path):
        """[M1.S6] SP명 검색 → 해당 SP를 참조하는 파일/라인/스니펫 반환"""
        from services.search_service import search_keyword
        project_files = _make_project_files(tmp_path, {
            'PaymentProject': {
                'PayRepo.cs': (
                    'public class PayRepo {\n'
                    '    void Run() {\n'
                    '        var cmd = new SqlCommand("UP_PAYMENT_TX_INS", conn);\n'
                    '    }\n'
                    '}\n'
                )
            }
        })
        result = search_keyword('UP_PAYMENT_TX_INS', project_files)
        assert isinstance(result, dict), "결과는 dict여야 합니다"
        # 검색어가 포함된 프로젝트 또는 파일이 결과에 있어야 함
        assert len(result) > 0, "검색 결과가 1건 이상이어야 합니다"

    def test_keyword_not_found_returns_empty(self, tmp_path):
        """없는 키워드 검색 → 빈 결과"""
        from services.search_service import search_keyword
        project_files = _make_project_files(tmp_path, {
            'Proj': {'File.cs': 'public class A {}'}
        })
        result = search_keyword('NOT_EXIST_KEYWORD_XYZ', project_files)
        assert result == {} or all(
            len(v) == 0 for v in result.values()
        ), "없는 키워드는 빈 결과를 반환해야 합니다"

    def test_empty_keyword_returns_empty(self, tmp_path):
        """[M1.S15] 빈 검색어 → 빈 결과, 예외 없음"""
        from services.search_service import search_keyword
        project_files = _make_project_files(tmp_path, {
            'Proj': {'File.cs': 'public class A {}'}
        })
        result = search_keyword('', project_files)
        assert isinstance(result, dict), "빈 검색어도 dict를 반환해야 합니다"

    def test_invalid_regex_mode_raises_value_error(self, tmp_path):
        """[M1.S16] 유효하지 않은 정규식 + regex_mode=True → ValueError"""
        from services.search_service import search_keyword
        project_files = _make_project_files(tmp_path, {
            'Proj': {'File.cs': 'public class A {}'}
        })
        import pytest
        with pytest.raises(ValueError, match="유효하지 않은 정규식"):
            search_keyword('[invalid(regex', project_files, regex_mode=True)

    def test_keyword_length_limit_raises_value_error(self, tmp_path):
        """키워드 길이 200자 초과 → ValueError"""
        from services.search_service import search_keyword
        project_files = _make_project_files(tmp_path, {
            'Proj': {'File.cs': 'public class A {}'}
        })
        import pytest
        long_keyword = 'A' * 201
        with pytest.raises(ValueError):
            search_keyword(long_keyword, project_files)


# ---------------------------------------------------------------------------
# [S-SR-05] 대용량 검색 성능 (search_keyword — 500개 파일)
# ---------------------------------------------------------------------------

class TestSearchPerformance:
    """search_keyword() — 500개 파일 기준 3초 이내 응답 [M1.AC 3.6]"""

    def test_search_500_files_within_3_seconds(self, tmp_path):
        """[M1.S17] .cs 파일 500개 대상 일반 키워드 검색 → 3초 이내"""
        from services.search_service import search_keyword
        # 500개 파일 생성
        proj_dir = tmp_path / 'BigProject'
        proj_dir.mkdir()
        project_files = {'BigProject': {}}
        for i in range(500):
            f = proj_dir / f'File{i}.cs'
            content = (
                f'public class Class{i} {{\n'
                f'    public void Method{i}() {{ var x = {i}; }}\n'
                f'}}\n'
            )
            f.write_text(content, encoding='utf-8')
            project_files['BigProject'][str(f)] = content

        start = time.time()
        search_keyword('Method100', project_files)
        elapsed = time.time() - start
        assert elapsed < 3.0, f"검색이 3초를 초과했습니다: {elapsed:.2f}초"
