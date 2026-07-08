# payletterCodeLab — PG 코드베이스 통합 분석기 발표 자료

> PG사 내부 C# 코드베이스를 통합 수집·분석·시각화하는 인텔리전스 도구

---

## 1. 프로젝트 개요

### 왜 만들었나

| 기존 문제 | 해결 방향 |
|---|---|
| 프로젝트마다 별도로 코드를 열어 수동 추적 | 여러 프로젝트를 한 번에 수집·분석 |
| SP 호출 흐름을 코드만 보고 파악 | SP→파일 / 파일→SP 양방향 시각화 |
| 순환복잡도(CC) 측정 도구가 없음 | Lizard 기반 자동 CC 측정 |
| 외부 SaaS 도구 사용 불가 (폐쇄망) | .exe 단일 파일로 오프라인 실행 |

### 핵심 특징

- **단일 .exe 실행** — Python + Flask를 PyInstaller로 번들링, 더블클릭 → `localhost:5000` 자동 오픈
- **폐쇄망 대응** — D3.js, Chart.js, Tailwind CSS 모두 로컬 파일 번들 (CDN 없음)
- **소스 3종 지원** — GitLab (사설망), GitHub, 로컬 폴더
- **분석 대상** — C# (.cs, .csproj) 전용

---

## 2. 전체 기술 스택

```
┌─────────────────────────────────────────────────────┐
│                   브라우저 (UI)                       │
│  Tailwind CSS (로컬)  │  D3.js v7 (로컬)             │
│  Chart.js v4 (로컬)   │  Jinja2 템플릿               │
└───────────────────────┬─────────────────────────────┘
                        │  HTTP / REST API
┌───────────────────────▼─────────────────────────────┐
│               Flask 3.x (백엔드)                     │
│  routes/           services/          analyzers/    │
│  source_routes     source_service     complexity    │
│  analyze_routes    analyze_service    sp_detector   │
│  graph_routes      result_cache       dependency    │
│  search_routes     github_client      flow_analyzer │
│  export_routes     gitlab_client                   │
└─────────────────────────────────────────────────────┘

사용 라이브러리:
  분석  : Lizard 1.17.x (CC 측정), openpyxl 3.x (Excel)
  소스  : python-gitlab 4.x, PyGithub 2.x
  서버  : Flask 3.x, PyInstaller 6.x
  UI    : D3.js v7, Chart.js v4, Tailwind CSS
```

### 아키텍처 원칙

- **Clean Architecture** — routes(라우팅) → services(비즈니스 로직) → analyzers(순수 함수)
- **Port-Adapter 패턴** — GitLab/GitHub/Local 어댑터를 동일 인터페이스(`SourceManager`)로 추상화
- **서버 메모리 캐시** — DB 없음, `AnalysisResultCache` 싱글톤으로 분석 결과 보관

---

## 3. 소스 연결 설정

### 화면 역할

프로젝트를 어디서 가져올지 설정하고 분석을 시작하는 진입점.

### 지원 소스 3종

| 탭 | 인증 방식 | 구현 클래스 |
|---|---|---|
| GitLab | URL + Personal Access Token + SSL 옵션 | `GitLabClient` / `GitLabMockClient` |
| GitHub | Personal Access Token (선택) | `GitHubClient` |
| 로컬 폴더 | 파일 경로 직접 입력 | `LocalFolderManager` |

### 연결 흐름 (GitHub 예시)

```
[브라우저]                    [Flask]                   [GitHub API]
   │                            │                            │
   │── POST /api/sources/        │                            │
   │   github/connect ─────────►│                            │
   │   { token: "..." }         │── socket 연결 시도 ────────►│
   │                            │   (api.github.com:443)     │
   │                            │   10초 타임아웃 내 성공    │
   │                            │                            │
   │                            │── PyGithub 인증 ──────────►│
   │                            │◄─ 레포지터리 목록 ──────────│
   │                            │                            │
   │◄── { projects: [...] } ────│                            │
   │    각 항목: name, id,      │                            │
   │    path(로컬 캐시 경로),   │                            │
   │    source_type: 'github'   │                            │
```

### 폐쇄망 감지 (GitHub)

```python
# github_client.py
def _check_network(self, timeout=10):
    try:
        with socket.create_connection(("api.github.com", 443), timeout=timeout):
            return True
    except (OSError, ConnectionError):
        return False
    # False → ConnectionError 발생 → UI에 "로컬 폴더로 전환하세요" 안내
```

### 분석 시작 흐름

```
사용자가 프로젝트 선택 → [분석 시작] 버튼
    │
    ├── POST /api/analyze/start  { projects: [...] }
    │
    ├── 백그라운드 스레드 시작 (30초 타임아웃)
    │       ├── GitHub 프로젝트: 로컬 클론 (ZIP 다운로드 + 압축해제)
    │       ├── 로컬 폴더: 경로 직접 참조
    │       └── GitLab: ZIP 아카이브 다운로드
    │
    ├── .cs 파일 수집 → 청크 단위(500개) 분석
    │
    └── AnalysisResultCache.set_results(프로젝트명, 결과)
```

### 로드된 프로젝트 관리 테이블

분석 완료 후 소스 설정 화면 하단에 표시:

| 프로젝트명 | 함수 수 | SP 호출 | 고위험 함수(CC 10+) | 상태 | 관리 |
|---|---|---|---|---|---|
| PayCore | 87 | 23 | 5 | 완료 | 제거 |
| SettleManager | 64 | 31 | 8 | 완료 | 제거 |

- 개별 제거: `DELETE /api/analyze/results/<project_name>`
- 전체 초기화: 모든 프로젝트 순차 제거

---

## 4. 통합 대시보드

### 화면 역할

분석 완료 직후 전체 코드베이스 현황을 한 눈에 파악.

### 표시 요소

```
┌─────┬─────┬─────┬─────┬─────┐
│프로  │파일  │함수  │위험  │SP   │  ← 요약 카드 5개
│젝트 수│ 수   │ 수   │함수 수│ 수  │
└─────┴─────┴─────┴─────┴─────┘
┌──────────────────┬────────────┐
│  D3.js Treemap   │ Chart.js   │  ← 좌: 파일별 CC 히트맵
│  (파일별 CC 히트맵)│ 도넛 차트  │     우: CC 등급 분포
└──────────────────┴────────────┘
┌──────────────────────────────┐
│  Chart.js 가로 바 차트        │  ← 프로젝트별 평균CC / 위험함수 비교
└──────────────────────────────┘
┌──────────────────────────────┐
│  위험 함수 테이블 (CC 내림차순)│  ← CC 10+ 함수 목록
└──────────────────────────────┘
```

### 사용 라이브러리 및 역할

| 라이브러리 | 역할 |
|---|---|
| **D3.js v7** | Treemap — 파일 크기(함수 수)에 비례한 사각형, CC 등급별 색상 히트맵 |
| **Chart.js v4** | 도넛 차트 (CC 등급 분포), 가로 바 차트 (프로젝트 비교) |

### CC 등급 색상 체계

| 등급 | CC 범위 | 색상 |
|---|---|---|
| 낮음 | 1 ~ 4 | `#22c55e` (success) |
| 중간 | 5 ~ 9 | `#f59e0b` (warning) |
| 높음 | 10 ~ 14 | `#ef4444` (danger) |
| 매우높음 | 15+ | `#991b1b` (danger-dark) |

### 데이터 흐름

```
GET /api/analyze/results
    → AnalysisResultCache.get_all_results()
    → { "PayCore": { complexity: [...], sp_calls: [...], ... }, ... }
    → JS가 집계 후 D3/Chart.js 렌더링
```

---

## 5. 복잡도 상세

### 화면 역할

프로젝트별·파일별 순환복잡도(CC) 상세 데이터 제공.

### 순환복잡도(CC)란?

```
CC = 코드 내 분기(if/for/while/case/&&/||) 수 + 1

예시:
  void Simple() { ... }           → CC = 1  (낮음)
  void Complex(int x) {
      if (x > 0) {                → +1
          for (int i=0; i<x; i++) → +1
              if (i%2==0) { ... } → +1
      }
  }                               → CC = 4  (낮음)
```

### 측정 도구: Lizard

```python
# complexity_analyzer.py
import lizard

def analyze_complexity(cs_files: list) -> list:
    results = []
    for file_path in cs_files:
        analysis = lizard.analyze_file(file_path)
        for func in analysis.function_list:
            results.append({
                'project': ...,
                'file': file_path,
                'class_name': func.name.split('::')[0],
                'function': func.name,
                'cc': func.cyclomatic_complexity,
                'lines': func.nloc,
                'grade': _grade(func.cyclomatic_complexity),
            })
    return results

def _grade(cc: int) -> str:
    if cc <= 4:  return '낮음'
    if cc <= 9:  return '중간'
    if cc <= 14: return '높음'
    return '매우높음'
```

### God Class 판정

```python
# 조건 1: 함수 수 >= 20
# 조건 2: 클래스 내 평균 CC >= 8
# 둘 중 하나라도 충족 → God Class
```

### 보안 민감 코드 분류

파일명 또는 함수명에 다음 키워드 포함 시 자동 분류:
- `Encrypt`, `Hash`, `Token`, `Auth`, `Secret`, `Key`

---

## 6. 전역 검색

### 화면 역할

분석된 전체 프로젝트의 모든 `.cs` 파일에서 즉시 검색.

### 검색 대상

- SP 호출명 (ex: `UP_PAY_NT_GET`)
- 클래스명, 메서드명
- 문자열 상수, 변수명

### 검색 흐름

```
사용자 입력: "UP_PAY"
    │
    ├── POST /api/search  { query: "UP_PAY", regex: false }
    │
    ├── search_service.search(query, use_regex=False)
    │       ├── AnalysisResultCache.get_all_results() → 메모리에서 즉시 가져옴
    │       ├── 각 프로젝트의 .cs 파일 순회
    │       │   └── re.search(re.escape("UP_PAY"), line) → 매칭 라인 수집
    │       └── 결과: [{project, file, line_num, snippet, cc}, ...]
    │
    └── 응답 반환 (500개 파일 기준 3초 이내)
```

### 정규식 모드

```
토글 ON → re.compile(query) 직접 사용
          잘못된 정규식 → HTTP 400 + "유효하지 않은 정규식" 메시지

토글 OFF → re.escape(query)로 특수문자 이스케이프 후 검색
```

### 결과 표시 구조

```
[PayCore 프로젝트]
  └── Repository/PayRepository.cs
        ├── Line 42: new SqlCommand("UP_PAY_NT_GET", conn)  CC: 8
        └── Line 87: cmd.CommandText = "UP_PAY_NT_INS";    CC: 12

[SettleManager 프로젝트]
  └── Services/SettlementService.cs
        └── Line 156: var result = db.Execute("UP_PAY_...")  CC: 16
```

SP 검색 결과 → "SP 흐름도로 이동" 딥링크 제공 (`/sp-flow?sp=UP_PAY_NT_GET`)

---

## 7. 의존성 흐름도

### 화면 역할

프로젝트 간 참조 관계를 그래프로 시각화. 순환 참조 탐지 포함.

### 데이터 추출 방법

```python
# dependency_analyzer.py — .csproj XML 파싱
import xml.etree.ElementTree as ET

def parse_csproj(csproj_path: str) -> dict:
    tree = ET.parse(csproj_path)
    root = tree.getroot()
    ns = {'': 'http://schemas.microsoft.com/developer/msbuild/2003'}

    # ProjectReference: 프로젝트 간 의존 관계
    project_refs = [
        ref.get('Include', '')
        for ref in root.findall('.//ProjectReference', ns)
    ]
    # PackageReference: NuGet 패키지 참조
    package_refs = [
        ref.get('Include', '')
        for ref in root.findall('.//PackageReference', ns)
    ]
    return {
        'name': 프로젝트명,
        'project_refs': project_refs,
        'package_refs': package_refs,
    }
```

### 순환 참조 탐지

```python
# DFS로 순환 탐지
def _detect_cycles(graph: dict) -> list:
    visited, rec_stack = set(), set()
    cycles = []

    def dfs(node, path):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path + [neighbor])
            elif neighbor in rec_stack:
                cycles.append(path)  # 순환 발견
        rec_stack.discard(node)

    for node in graph:
        if node not in visited:
            dfs(node, [node])
    return cycles
```

### D3.js Force-Directed 그래프

```
GET /api/graph/dependency
    → { nodes: [{id, name, depth}, ...], edges: [{source, target}, ...] }

D3.js 시각화:
  노드 = 프로젝트 (원)
    - 크기: 고정
    - 색상: 일반=primary, 순환참조=danger
    - 숫자: 의존성 깊이(Depth)
  엣지 = 참조 방향 (화살표)
    - 순환참조 엣지: danger 색상 강조

인터랙션:
  - 줌/패닝: d3.zoom()
  - 노드 클릭: 포커스 모드 (직접 연결 노드만 표시, 나머지 흐리게)
  - 드래그: 노드 위치 이동
```

### API 데이터 구조

```json
{
  "nodes": [
    { "id": "PayCore", "depth": 0 },
    { "id": "SettleManager", "depth": 1 },
    { "id": "MerchantPortal", "depth": 1 }
  ],
  "edges": [
    { "source": "SettleManager", "target": "PayCore" },
    { "source": "MerchantPortal", "target": "PayCore" }
  ]
}
```

---

## 8. 호출 흐름도

### 화면 역할

파일/클래스 간 메서드 호출 관계를 방향 그래프로 시각화.

### 데이터 추출 방법

```python
# flow_analyzer.py — 정규식 기반 호출 패턴 탐지
import re

# 탐지 패턴 예시
INSTANCE_PATTERN = re.compile(
    r'(?:new\s+(\w+)\s*\(|(\w+)\s+\w+\s*=\s*new\s+(\w+)\s*\()'
)
METHOD_CALL_PATTERN = re.compile(
    r'(\w+)\.\s*(\w+)\s*\('
)

def extract_call_graph(cs_files: list) -> dict:
    nodes, edges = [], []
    for file_path in cs_files:
        caller = os.path.basename(file_path)  # 노드 = 파일명(클래스)
        with open(file_path, encoding='utf-8', errors='ignore') as f:
            for line in f:
                for match in METHOD_CALL_PATTERN.finditer(line):
                    callee = match.group(1)
                    if callee != caller:
                        edges.append({
                            'caller': caller,
                            'callee': callee,
                        })
    return {'nodes': nodes, 'edges': edges}
```

### 핵심 버그 수정 이력

```
[수정 전] flow_analyzer.py: edges = {caller, callee}
          graph_routes.py:  JS에 {caller, callee} 그대로 반환
          flow.html JS:     e.source, e.target 읽음
          → 항상 undefined → BFS 빈 인접 리스트 → 시작 노드 1개만 표시

[수정 후] graph_routes.py flow_class()에서 키 변환:
    edges.append({
        'source': e.get('caller', ''),
        'target': e.get('callee', ''),
    })
```

### D3.js 방향 그래프

```
GET /api/graph/flow/class
    → { nodes: [...], edges: [{source, target}, ...] }

D3.js 시각화:
  노드 = 파일/클래스
    - 크기: 다른 클래스로부터의 참조 빈도에 비례
    - 색상: 해당 파일의 평균 CC 등급 반영
    - 테두리: 결제 관련 파일(Payment/Settle/Approve/...) → primary 색상
  엣지 = 호출 방향 화살표

인터랙션:
  - 시작 함수 선택 → BFS로 1~2단계 연결 노드만 필터링
  - 노드 클릭 → 우측 사이드패널: 파일명, CC 상세, 함수 목록
  - 줌/패닝/드래그
```

### 시작 함수 선택 후 BFS 흐름

```
선택: SettlementService
    │
    BFS 1단계: SettlementService → [SettleRepository, PaymentClient]
    BFS 2단계: SettleRepository → [DbConnection]
              PaymentClient    → [HttpClient]
    │
    → 이 5개 노드 + 연결 엣지만 표시
    → 나머지 노드 제거 (투명 처리)
```

---

## 9. SP 흐름도

### 화면 역할

C# 코드에서 SP 호출을 자동 탐지, SP↔파일 양방향 탐색 제공.

### SP 탐지 패턴 (정규식)

```python
# sp_detector.py
SP_PATTERNS = [
    # SqlCommand 생성자
    re.compile(r'new\s+SqlCommand\s*\(\s*["\'](\w+)["\']'),
    # Dapper Execute/Query
    re.compile(r'\.(?:Execute|Query|QueryFirst)\w*\s*\(\s*["\'](\w+)["\']'),
    # cmd.CommandText 할당
    re.compile(r'CommandText\s*=\s*["\'](\w+)["\']'),
    # 문자열 상수로 SP명 전달
    re.compile(r'["\'](\bUP_[A-Z_]+\b)["\']'),
]
```

### 탐지 예시 (샘플 프로젝트 기준)

```csharp
// SettleRepository.cs
new SqlCommand("UP_STL_MM_GET", conn)     → 탐지: UP_STL_MM_GET
connection.Execute("UP_STL_MM_INS", ...)  → 탐지: UP_STL_MM_INS
cmd.CommandText = "UP_STL_DY_UPD"        → 탐지: UP_STL_DY_UPD
```

### SP 명명 규칙 (사내 컨벤션)

```
UP_{DOMAIN}_{TABLE}_{VERB}

UP_PAY_NT_GET   → 결제(PAY) / NT테이블 / 조회
UP_STL_MM_INS   → 정산(STL) / MM테이블 / 등록
UP_MER_INFO_UPD → 가맹점(MER) / INFO테이블 / 수정
```

### 결제/정산 관련 SP 자동 분류

SP명에 `PAYMENT`, `SETTLE`, `APPROVE`, `CANCEL`, `REFUND` 포함 시 primary 색상으로 강조.

### D3.js 방사형 그래프

```
GET /api/graph/flow/sp
    → { sp_calls: [{sp_name, file, class, method, line}, ...] }

시각화:
  중앙 노드 = 선택한 SP
  외부 노드 = 해당 SP를 호출하는 메서드
    - 색상: 호출 메서드의 CC 등급
  화살표: 호출 방향 (메서드 → SP)

좌측 패널:
  SP 전체 목록 (이름 필터 실시간 검색)
  Dead SP (호출자 없음): 취소선 표시

우측 패널:
  선택 SP의 호출 위치 테이블
  (메서드명 / 클래스 / 파일 / 프로젝트 / CC / 라인)
  메서드명 클릭 → 호출 흐름도 딥링크
```

### 양방향 탐색

```
SP → 파일 방향: "이 SP를 어떤 파일이 호출하는가?"
    선택: UP_STL_MM_GET
    결과: SettlementService.cs (CreateDailySettle, CC:16)
          SettleController.cs (GetList, CC:7)

파일 → SP 방향: "이 파일이 어떤 SP를 호출하는가?"
    선택: SettlementService.cs
    결과: UP_STL_MM_GET, UP_STL_MM_INS, UP_STL_DY_UPD, ...
```

---

## 10. 전체 데이터 흐름 요약

```
[소스 연결 설정]
  GitHub/GitLab/로컬 → 프로젝트 목록 조회
  분석 시작 → 클론 → .cs 파일 수집

        ↓  분석 엔진 (analyzers/)

  Lizard          → complexity[]    (함수별 CC)
  sp_detector     → sp_calls[]      (SP 호출 위치)
  flow_analyzer   → call_graph{}    (호출 그래프)
  dependency_analyzer → dependency_graph{}  (.csproj 의존성)

        ↓  AnalysisResultCache (서버 메모리)

  { "PayCore": { complexity, sp_calls, call_graph, dependency_graph } }

        ↓  REST API

  GET /api/analyze/results   → 통합 대시보드, 복잡도 상세
  POST /api/search           → 전역 검색
  GET /api/graph/dependency  → 의존성 흐름도
  GET /api/graph/flow/class  → 호출 흐름도
  GET /api/graph/flow/sp     → SP 흐름도
  GET /api/export/excel      → Excel 5개 시트 다운로드
```

---

## 11. Excel 내보내기

분석 완료 후 전체 결과를 Excel 파일로 다운로드.

| 시트 | 내용 |
|---|---|
| 전체 함수 목록 | 프로젝트/파일/클래스/함수명/CC/등급/라인 수, CC 등급별 셀 색상 |
| 위험 함수 목록 | CC 10+ 함수만 필터링, CC 내림차순 정렬 |
| God Class 목록 | 클래스명/프로젝트/함수 수/평균 CC/판정 이유 |
| SP 사용 현황 | SP명/사용 프로젝트/파일 경로/라인 번호/호출 메서드 |
| 프로젝트별 요약 | 파일 수/함수 수/평균 CC/최대 CC/위험 함수 수/God Class 수/SP 수 |

파일명: `payletterCodeLab_Report_{YYYYMMDD_HHMMSS}.xlsx`

---

## 12. 보안 설계

| 항목 | 구현 |
|---|---|
| GitLab/GitHub Token | 서버 메모리에만 보관, 파일·로그·응답 JSON 기록 금지 |
| 로그 마스킹 | `TokenMaskingFilter`로 token/access_token 키 자동 제거 |
| Path Traversal 방지 | `os.path.abspath()` 정규화 + 경계 경로 검증 |
| URL 검증 | `urllib.parse`로 파싱 후 scheme 검증 (http/https만 허용) |
| 검색 키워드 | 길이 제한 200자 + `re.escape()` 처리 |
| XSS 방어 | Jinja2 자동 이스케이핑 활성화 |
| 보안 헤더 | X-Frame-Options, X-Content-Type-Options, CSP, Referrer-Policy |

---

*발표 자료 생성일: 2026-07-07 | payletterCodeLab v1.30.0*
