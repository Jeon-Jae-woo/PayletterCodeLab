"""
통합 테스트 공통 헬퍼 함수 — conftest.py와 테스트 파일에서 임포트 가능.
"""
import os
import time


def make_cs_files(directory, count=5, sp_name='PaymentSP'):
    """테스트용 .cs 파일 생성 — 복잡도·SP 탐지 패턴 포함.

    Args:
        directory: 파일을 생성할 Path 객체 또는 str 경로
        count: 생성할 .cs 파일 수
        sp_name: 파일에 삽입할 SP명 (sp_detector 탐지용)

    Returns:
        directory 경로 str
    """
    target = str(directory)
    for i in range(count):
        content = (
            f'using System;\n'
            f'using System.Data.SqlClient;\n'
            f'namespace TestProject{i} {{\n'
            f'    public class TestClass{i} {{\n'
            f'        public void Execute{i}() {{\n'
            f'            // SP 호출 패턴 — sp_detector 탐지 대상 [M1.AC 6.1]\n'
            f'            var cmd = new SqlCommand("{sp_name}", conn);\n'
            f'            cmd.CommandType = System.Data.CommandType.StoredProcedure;\n'
            f'            // 복잡도 생성 (Lizard CC 측정 대상)\n'
            f'            for (int j = 0; j < 10; j++) {{\n'
            f'                if (j % 2 == 0) {{\n'
            f'                    Console.WriteLine(j);\n'
            f'                }}\n'
            f'            }}\n'
            f'        }}\n'
            f'    }}\n'
            f'}}\n'
        )
        filepath = os.path.join(target, f'TestClass{i}.cs')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    return target


def wait_for_analysis(timeout=20):
    """백그라운드 분석 스레드 완료 대기 — 최대 timeout초 폴링.

    Returns:
        True: 완료 / False: 타임아웃
    """
    from services import analyze_service
    thread = analyze_service._analysis_thread
    if thread is None:
        return True
    thread.join(timeout=timeout)
    return not thread.is_alive()
