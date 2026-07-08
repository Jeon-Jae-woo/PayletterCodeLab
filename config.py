"""
환경 변수 기반 설정 로더 — [GR-1.4] 보안 Hard Block 준수

규칙:
  - .env 파일 직접 오픈 금지 ([GR-1.4])
  - python-dotenv 의존 금지 ([GR-1.4] §4.2)
  - 토큰/시크릿 하드코딩 금지 ([PR-6] Secret Management)
  - 모든 값은 os.environ 에서만 로드

환경 변수 목록:
  GITLAB_MOCK      - "true" 시 GitLabMockClient 사용 (로컬 개발용)
  GITHUB_DISABLED  - "true" 시 GitHub 소스 유형 비활성화 (폐쇄망 명시 설정)
  GITLAB_TOKEN     - GitLab Personal Access Token (메모리에만 보관)
  GITLAB_URL       - GitLab 서버 URL (예: https://gitlab.company.com)
  GITLAB_SSL_VERIFY - "false" 시 SSL 검증 비활성화 (사설 인증서 환경 한정)
  GITHUB_TOKEN     - GitHub Personal Access Token (메모리에만 보관)
"""
import os
from typing import Dict, Union


def get_config() -> Dict[str, Union[str, bool]]:
    """
    환경 변수에서 설정값을 읽어 딕셔너리로 반환.
    토큰은 메모리에만 보관 — 파일/로그 기록 절대 금지 ([PR-6]).
    """
    return {
        # GitLab Mock 분기 (로컬 개발 환경 전용)
        'GITLAB_MOCK': os.environ.get('GITLAB_MOCK', '').lower() == 'true',

        # GitHub 비활성화 플래그 (폐쇄망 명시 설정 — config-externalize 계약)
        'GITHUB_DISABLED': os.environ.get('GITHUB_DISABLED', '').lower() == 'true',

        # GitLab 연결 설정
        'GITLAB_TOKEN': os.environ.get('GITLAB_TOKEN', ''),
        'GITLAB_URL': os.environ.get('GITLAB_URL', ''),
        'GITLAB_SSL_VERIFY': os.environ.get('GITLAB_SSL_VERIFY', 'true').lower() != 'false',

        # GitHub 연결 설정
        'GITHUB_TOKEN': os.environ.get('GITHUB_TOKEN', ''),
    }
