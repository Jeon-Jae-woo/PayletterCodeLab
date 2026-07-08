"""
T3 > T3.0.2 — AnalysisResultCache 공통 모듈 테스트

[M1.F7] 분석 결과 캐시 공통 모듈 (서버 메모리 싱글톤)
[M1.AC 1.4] 스레드 세이프 상태 관리
"""
import os
import sys
import threading

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# 픽스처: 각 테스트 전후로 캐시 초기화 (전역 상태 격리)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_cache():
    """각 테스트 전에 AnalysisResultCache를 초기화하여 전역 상태 격리"""
    from services.result_cache import AnalysisResultCache
    AnalysisResultCache.clear()
    yield
    AnalysisResultCache.clear()


# ---------------------------------------------------------------------------
# [S-RC-01] Normal — set_results() + get_results()
# ---------------------------------------------------------------------------

class TestSetAndGetResults:
    """AnalysisResultCache.set_results() / get_results() 기본 동작"""

    def test_set_and_get_returns_stored_value(self):
        """[S-RC-01] set_results() 후 get_results()로 동일 데이터를 반환해야 함"""
        from services.result_cache import AnalysisResultCache
        data = {'functions': [{'name': 'Foo', 'cc': 3}], 'total': 1}
        AnalysisResultCache.set_results('proj_a', data)
        result = AnalysisResultCache.get_results('proj_a')
        assert result == data, "저장된 분석 결과와 조회 결과가 일치해야 합니다"

    def test_get_results_returns_none_for_missing_project(self):
        """[S-RC-05] 없는 프로젝트 조회 시 None을 반환해야 함"""
        from services.result_cache import AnalysisResultCache
        result = AnalysisResultCache.get_results('nonexistent_project_xyz')
        assert result is None, "없는 프로젝트는 None을 반환해야 합니다"

    def test_set_results_overwrites_existing(self):
        """같은 프로젝트에 set_results() 재호출 시 덮어쓰기"""
        from services.result_cache import AnalysisResultCache
        AnalysisResultCache.set_results('proj_b', {'total': 1})
        AnalysisResultCache.set_results('proj_b', {'total': 999})
        result = AnalysisResultCache.get_results('proj_b')
        assert result == {'total': 999}, "마지막 저장 값이 반환되어야 합니다"

    def test_multiple_projects_stored_independently(self):
        """여러 프로젝트 결과가 독립적으로 저장되어야 함"""
        from services.result_cache import AnalysisResultCache
        AnalysisResultCache.set_results('proj_x', {'total': 10})
        AnalysisResultCache.set_results('proj_y', {'total': 20})
        assert AnalysisResultCache.get_results('proj_x') == {'total': 10}
        assert AnalysisResultCache.get_results('proj_y') == {'total': 20}


# ---------------------------------------------------------------------------
# [S-RC-02] Normal — get_all_results()
# ---------------------------------------------------------------------------

class TestGetAllResults:
    """AnalysisResultCache.get_all_results() — 전체 병합 결과"""

    def test_get_all_returns_all_stored_projects(self):
        """[S-RC-02] 저장된 모든 프로젝트가 병합 dict로 반환되어야 함"""
        from services.result_cache import AnalysisResultCache
        AnalysisResultCache.set_results('pa', {'total': 1})
        AnalysisResultCache.set_results('pb', {'total': 2})
        all_results = AnalysisResultCache.get_all_results()
        assert 'pa' in all_results, "pa 프로젝트가 포함되어야 합니다"
        assert 'pb' in all_results, "pb 프로젝트가 포함되어야 합니다"
        assert all_results['pa'] == {'total': 1}
        assert all_results['pb'] == {'total': 2}

    def test_get_all_returns_empty_dict_when_no_results(self):
        """[S-RC-08] 캐시가 비어 있을 때 빈 dict를 반환해야 함"""
        from services.result_cache import AnalysisResultCache
        all_results = AnalysisResultCache.get_all_results()
        assert all_results == {}, "빈 캐시에서 빈 dict를 반환해야 합니다"

    def test_get_all_returns_copy_not_reference(self):
        """[S-RC-09] get_all_results()가 복사본을 반환해야 함 — 외부 변경에 격리"""
        from services.result_cache import AnalysisResultCache
        AnalysisResultCache.set_results('proj_iso', {'total': 5})
        snapshot = AnalysisResultCache.get_all_results()
        snapshot['proj_iso'] = {'total': 9999}  # 외부에서 변경
        # 캐시 원본은 영향받지 않아야 함
        original = AnalysisResultCache.get_results('proj_iso')
        assert original == {'total': 5}, "외부 변경이 캐시 원본에 영향을 주어서는 안 됩니다"


# ---------------------------------------------------------------------------
# [S-RC-03, S-RC-06] Normal/Exception — is_analysis_complete()
# ---------------------------------------------------------------------------

class TestIsAnalysisComplete:
    """AnalysisResultCache.is_analysis_complete() — 분석 완료 여부 판단"""

    def test_is_complete_returns_true_when_results_exist(self):
        """[S-RC-03] 분석 결과가 1개 이상 존재하면 True를 반환해야 함"""
        from services.result_cache import AnalysisResultCache
        AnalysisResultCache.set_results('proj_done', {'total': 3})
        assert AnalysisResultCache.is_analysis_complete() is True, \
            "결과가 존재할 때 is_analysis_complete()가 True를 반환해야 합니다"

    def test_is_complete_returns_false_when_empty(self):
        """[S-RC-06] 결과가 없으면 False를 반환해야 함"""
        from services.result_cache import AnalysisResultCache
        assert AnalysisResultCache.is_analysis_complete() is False, \
            "캐시가 비어 있을 때 is_analysis_complete()가 False를 반환해야 합니다"

    def test_is_complete_false_after_clear(self):
        """clear() 후에는 is_analysis_complete()가 False여야 함"""
        from services.result_cache import AnalysisResultCache
        AnalysisResultCache.set_results('proj_c', {'total': 1})
        AnalysisResultCache.clear()
        assert AnalysisResultCache.is_analysis_complete() is False, \
            "clear() 후 is_analysis_complete()가 False여야 합니다"


# ---------------------------------------------------------------------------
# [S-RC-04] Normal — clear()
# ---------------------------------------------------------------------------

class TestClear:
    """AnalysisResultCache.clear() — 전체 캐시 소거"""

    def test_clear_removes_all_results(self):
        """[S-RC-04] clear() 후 get_results()가 None을 반환해야 함"""
        from services.result_cache import AnalysisResultCache
        AnalysisResultCache.set_results('p1', {'total': 1})
        AnalysisResultCache.set_results('p2', {'total': 2})
        AnalysisResultCache.clear()
        assert AnalysisResultCache.get_results('p1') is None
        assert AnalysisResultCache.get_results('p2') is None

    def test_clear_on_empty_cache_is_safe(self):
        """빈 캐시에서 clear() 호출 시 예외 없이 동작해야 함"""
        from services.result_cache import AnalysisResultCache
        AnalysisResultCache.clear()  # 이미 비어 있음 — 예외 없어야 함
        assert AnalysisResultCache.get_all_results() == {}


# ---------------------------------------------------------------------------
# [S-RC-07] Boundary — 스레드 세이프 동시 접근
# ---------------------------------------------------------------------------

class TestThreadSafety:
    """AnalysisResultCache 스레드 세이프 동시 쓰기 검증 [M1.AC 1.4]"""

    def test_concurrent_set_results_no_corruption(self):
        """[S-RC-07] 20 스레드 동시 set_results() 시 데이터 손상 없음"""
        from services.result_cache import AnalysisResultCache
        errors = []

        def worker(name: str, value: int) -> None:
            try:
                AnalysisResultCache.set_results(name, {'total': value})
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(f'tc_proj_{i}', i))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"동시 쓰기 중 오류 발생: {errors}"
        # 모든 20개 프로젝트가 저장되어야 함
        for i in range(20):
            result = AnalysisResultCache.get_results(f'tc_proj_{i}')
            assert result is not None, f"tc_proj_{i} 결과가 저장되어야 합니다"
            assert result['total'] == i, f"tc_proj_{i} 값이 올바르게 저장되어야 합니다"
