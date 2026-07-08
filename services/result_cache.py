"""
[M1.F7] 분석 결과 캐시 공통 모듈 — 서버 메모리 싱글톤

분석 완료된 프로젝트 결과를 Flask 프로세스 생명주기 동안 메모리에 보관한다.
클래스 변수를 공유 상태로 사용하는 싱글톤 패턴이며, threading.Lock으로
동시 쓰기 보호([M1.AC 1.4])를 보장한다.
"""
import threading
from typing import Dict, Optional


class AnalysisResultCache:
    """분석 결과 서버 메모리 싱글톤 캐시.

    모든 메서드가 클래스 메서드로 구현되어 인스턴스 생성 없이 사용한다.
    _cache: 프로젝트명 → 분석 결과 dict 매핑
    _lock: 동시 쓰기 보호용 스레드 락
    """

    _cache: Dict[str, dict] = {}
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def set_results(cls, project_name: str, result_data: dict) -> None:
        """분석 결과를 캐시에 저장한다. 기존 값은 덮어쓴다."""
        with cls._lock:
            cls._cache[project_name] = result_data

    @classmethod
    def get_results(cls, project_name: str) -> Optional[dict]:
        """프로젝트 분석 결과를 반환한다. 없으면 None."""
        with cls._lock:
            return cls._cache.get(project_name)

    @classmethod
    def get_all_results(cls) -> dict:
        """저장된 모든 프로젝트 결과를 복사본으로 반환한다.

        외부 변경이 캐시 원본에 영향을 주지 않도록 얕은 복사본을 반환한다.
        """
        with cls._lock:
            return dict(cls._cache)

    @classmethod
    def is_analysis_complete(cls) -> bool:
        """분석 결과가 1개 이상 존재하면 True를 반환한다."""
        with cls._lock:
            return len(cls._cache) > 0

    @classmethod
    def remove(cls, project_name: str) -> bool:
        """특정 프로젝트 결과를 캐시에서 제거한다. 존재하지 않으면 False."""
        with cls._lock:
            if project_name not in cls._cache:
                return False
            del cls._cache[project_name]
            return True

    @classmethod
    def clear(cls) -> None:
        """캐시 전체를 소거한다. 앱 재시작 또는 재분석 시 호출한다."""
        with cls._lock:
            cls._cache.clear()
