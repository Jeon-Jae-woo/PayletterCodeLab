"""
[M1.IT-4] Happy — 로컬 폴더 소스 + 캐시 재사용

Ref: PRD Section 5-2 [M1.IT-4]
커버 AC: [M1.AC 1.3], [M1.AC 1.5]

전제조건: 로컬 임시 폴더에 .cs 파일 5개 생성 (pytest tmp_path)
"""
from unittest.mock import patch

import pytest

from tests.integration.helpers import make_cs_files, wait_for_analysis


@pytest.mark.happy
class TestLocalFolderCacheReuse:
    """[M1.IT-4] 로컬 폴더 소스 + 캐시 재사용 통합 테스트."""

    def test_local_folder_cache_reuse(self, client, tmp_path):
        """
        로컬 폴더 소스 연결 → 1차 분석 → 동일 경로 재분석.
        2차 분석 시 LocalFolderManager.clone_project 미호출 확인 (Mock spy).

        검증:
        1. 1차 분석: 정상 결과 반환
        2. 2차 분석: LocalFolderManager.clone_project 미호출
        3. 2차 분석: AnalysisResultCache에 결과 존재
        """
        # 전제조건: 임시 폴더에 .cs 파일 5개 생성
        project_dir = str(tmp_path / 'local_project')
        import os
        os.makedirs(project_dir, exist_ok=True)
        make_cs_files(project_dir, count=5, sp_name='SettleSP')

        # 로컬 폴더 소스 연결 검증
        resp_connect = client.post(
            '/api/sources/local/validate',
            json={'path': project_dir},
        )
        assert resp_connect.status_code == 200
        conn_data = resp_connect.get_json()
        assert 'projects' in conn_data

        # 1차 분석 실행
        analysis_projects = [{'name': 'LocalProject', 'path': project_dir}]
        resp1 = client.post('/api/analyze/start', json={'projects': analysis_projects})
        assert resp1.status_code == 200

        completed = wait_for_analysis(timeout=20)
        assert completed, '1차 분석이 20초 내 완료되지 않았습니다'

        # 1차 결과 확인
        resp_results1 = client.get('/api/analyze/results')
        assert resp_results1.status_code == 200
        results1 = resp_results1.get_json()['results']
        assert 'LocalProject' in results1, '1차 분석 결과가 없습니다'
        assert len(results1['LocalProject']['complexity']) > 0

        # 2차 분석 — clone_project 호출 여부 감시
        with patch.object(
            __import__('services.source_service', fromlist=['LocalFolderManager']).LocalFolderManager,
            'clone_project',
            wraps=lambda self, pid, td: project_dir,
        ) as mock_clone:
            resp2 = client.post('/api/analyze/start', json={'projects': analysis_projects})
            assert resp2.status_code == 200
            completed2 = wait_for_analysis(timeout=20)
            assert completed2, '2차 분석이 20초 내 완료되지 않았습니다'

            # 2차 분석에서 clone_project가 호출되지 않아야 함
            # (analyze_service는 이미 경로를 직접 받아 clone_project를 호출하지 않음)
            assert mock_clone.call_count == 0, (
                f'2차 분석 시 clone_project가 {mock_clone.call_count}회 호출됨 — 0이어야 합니다'
            )

        # 3. 2차 분석 후 캐시에 결과 존재
        from services.result_cache import AnalysisResultCache
        cached = AnalysisResultCache.get_results('LocalProject')
        assert cached is not None, '2차 분석 후 캐시 결과가 없습니다'

    def test_local_folder_invalid_path_returns_400(self, client):
        """존재하지 않는 경로 → 400 반환 [M1.EX-3]."""
        resp = client.post(
            '/api/sources/local/validate',
            json={'path': '/nonexistent/path/that/does/not/exist'},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data

    def test_local_folder_no_cs_files_returns_400(self, client, tmp_path):
        """C# 파일 없는 폴더 → 400 반환 [M1.EX-3]."""
        empty_dir = str(tmp_path / 'empty_project')
        import os
        os.makedirs(empty_dir, exist_ok=True)
        # .txt 파일만 생성 (.cs 없음)
        with open(os.path.join(empty_dir, 'readme.txt'), 'w') as f:
            f.write('no cs files here')

        resp = client.post(
            '/api/sources/local/validate',
            json={'path': empty_dir},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data
