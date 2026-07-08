"""
통합 테스트 공통 픽스처 — [PR-4] Integration Test Configuration

데이터 격리: pytest tmp_path fixture 사용 (테스트별 임시 디렉터리 생성 + 자동 정리)
Mock 경계: GITLAB_MOCK=true 환경 변수 기반 GitLabMockClient 활성화
"""
import os
import sys

import pytest

# 프로젝트 루트를 sys.path에 추가 — 절대 임포트 보장
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.integration.helpers import make_cs_files


# ---------------------------------------------------------------------------
# 앱 픽스처
# ---------------------------------------------------------------------------

@pytest.fixture(scope='session')
def app():
    """Flask 테스트 앱 — 세션 단위 싱글톤."""
    from app import create_app
    return create_app({'TESTING': True})


@pytest.fixture
def client(app):
    """Flask 테스트 클라이언트 — 테스트마다 새 요청 컨텍스트."""
    return app.test_client()


# ---------------------------------------------------------------------------
# 캐시 격리 픽스처
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_analysis_cache():
    """테스트 전후 AnalysisResultCache 소거 — 테스트 간 오염 방지."""
    from services.result_cache import AnalysisResultCache
    AnalysisResultCache.clear()
    yield
    AnalysisResultCache.clear()


# ---------------------------------------------------------------------------
# 분석 결과 사전 로드 픽스처 (IT-2, IT-3 전제조건)
# ---------------------------------------------------------------------------

@pytest.fixture
def preloaded_cache(tmp_path):
    """분석 완료 상태 시뮬레이션 — AnalysisResultCache에 샘플 결과 사전 로드.

    IT-2 (전역 검색), IT-3 (Excel 내보내기) 등 분석 완료 전제조건이
    필요한 테스트에서 사용.
    """
    from services.result_cache import AnalysisResultCache

    project_dir = str(tmp_path / 'preloaded_project')
    os.makedirs(project_dir, exist_ok=True)
    make_cs_files(project_dir, count=3, sp_name='PaymentSP')

    sample_result = {
        'complexity': [
            {
                'file_path': os.path.join(project_dir, 'TestClass0.cs'),
                'functions': [
                    {'name': 'Execute0', 'cc': 3, 'cc_grade': '낮음',
                     'class_name': 'TestClass0', 'file_path': os.path.join(project_dir, 'TestClass0.cs')},
                ],
                'class_name': 'TestClass0',
                'project': 'PreloadedProject',
            }
        ],
        'sp_calls': [
            {
                'sp_name': 'PaymentSP',
                'file_path': os.path.join(project_dir, 'TestClass0.cs'),
                'line_no': 7,
                'class_name': 'TestClass0',
                'method_name': 'Execute0',
                'project': 'PreloadedProject',
                'category': 'payment',
            }
        ],
        'call_graph': {
            'nodes': [{'id': 'TestClass0::Execute0', 'label': 'Execute0',
                       'class_name': 'TestClass0', 'file_path': os.path.join(project_dir, 'TestClass0.cs'),
                       'cc': 3, 'is_payment': False, 'has_sp_call': True}],
            'edges': [],
        },
        'dependency_graph': {
            'nodes': [{'id': 'PreloadedProject', 'label': 'PreloadedProject', 'type': 'project'}],
            'edges': [],
        },
    }
    AnalysisResultCache.set_results('PreloadedProject', sample_result)
    return sample_result
