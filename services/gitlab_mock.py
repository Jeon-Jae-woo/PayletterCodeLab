"""
GitLab Mock 어댑터 — 로컬 개발 환경 전용 [PR-3] EnvironmentDivergence

내부 GitLab 서버가 폐쇄망 사설망에만 존재하여 로컬 개발 PC에서 접근 불가.
이 Mock은 실제 API 호출 없이 샘플 데이터를 반환하여 서비스 레이어 개발·테스트를 지원.
운영(production)에서는 GitLabClient로 교체됨 (Composition Root 분기).
"""
from typing import List, Dict

from services.source_service import SourceManager


class GitLabMockClient(SourceManager):
    """
    GitLab Mock 어댑터. 네트워크 없이 항상 성공 응답을 반환.
    GITLAB_MOCK=true 환경 변수 시 Composition Root에서 선택.
    """

    # 로컬 테스트·개발용 샘플 프로젝트 목록
    _SAMPLE_PROJECTS: List[Dict] = [
        {'id': '1', 'name': 'PaymentService', 'path': 'pg/payment-service'},
        {'id': '2', 'name': 'AuthService', 'path': 'pg/auth-service'},
        {'id': '3', 'name': 'SettlementCore', 'path': 'pg/settlement-core'},
        {'id': '4', 'name': 'SecurityGateway', 'path': 'pg/security-gateway'},
    ]

    def connect(self, **kwargs) -> bool:
        """Mock 연결 — 항상 성공. 실제 네트워크 호출 없음."""
        return True

    def list_projects(self) -> List[Dict]:
        """샘플 프로젝트 목록 반환 (읽기 전용 복사본)."""
        return list(self._SAMPLE_PROJECTS)

    def clone_project(self, project_id: str, target_dir: str) -> str:
        """
        Mock 클론 — 실제 파일 다운로드 없이 target_dir를 반환.
        실제 Clone은 GitLabClient에서 ZIP 다운로드 방식으로 구현 (T3 예정).
        """
        return target_dir
