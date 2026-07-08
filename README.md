# PayletterCodeLab

C# 코드베이스 통합 분석 도구.
SP 추적, 복잡도 측정, 프로젝트 간 의존성 시각화

---

## 주요 기능

| 기능 | 설명 |
|---|---|
| **통합 대시보드** | 전체 프로젝트 요약 (파일 수, 함수 수, SP 수, 복잡도 분포) |
| **복잡도 분석** | Lizard 기반 순환복잡도(CC) 측정, 위험 함수 / God Class 식별 |
| **SP 흐름도** | C# 코드에서 SP 호출 패턴 탐지, Dead SP 식별, 호출 흐름 시각화 |
| **의존성 흐름도** | .csproj 기반 프로젝트 간 의존성 그래프 (D3.js 네트워크) |
| **호출 흐름도** | 파일/클래스/메서드 단위 호출 흐름 분석 |
| **전역 검색** | 키워드 기반 코드 전체 검색 (SP명, 클래스명, 메서드명) |
| **Excel 내보내기** | 분석 결과 5개 시트 Excel 파일 생성 |

---

## 소스 연결 방식

3가지 소스 유형을 지원한다.

| 유형 | 설명 | 인증 |
|---|---|---|
| **GitLab** | 사설 인증서 + Personal Access Token | PAT |
| **GitHub** | Personal Access Token 또는 공개 레포 | PAT / 없음 |
| **로컬 폴더** | 이미 클론된 프로젝트 경로 직접 지정 | 없음 |

> **폐쇄망 제약:** 실행 환경(폐쇄망 PC)에서는 GitHub 외부 인터넷 차단으로 로컬 폴더 방식 권장.

---

## 분석 대상

- **언어:** C# (.NET Framework / .NET Core)
- **파일:** `.cs`, `.csproj`
- **분석 범위:** 클래스, 메서드, SP 호출 패턴, 프로젝트 참조 관계

---

## SP 탐지 로직

### 탐지 패턴 (Active SP)

코드에서 다음 4가지 문자열 리터럴 패턴을 탐지한다.

```csharp
new SqlCommand("UP_PAY_TX_INS", conn)       // SqlCommand 생성자
cmd.CommandText = "UP_PAY_TX_GET"           // CommandText 대입
conn.Execute("UP_PAY_TX_UPD", param)        // Dapper Execute
conn.Query("UP_TXN_LDG_LST", param)         // Dapper Query / QueryFirstOrDefault
```

### Dead SP 판단

```
const/readonly string 선언으로만 등장하고
실행 패턴(SqlCommand/Execute/Query)에서 발견되지 않은 SP
```

```csharp
// Dead SP 예시 — 선언만 있고 실행 없음
public const string SP_OLD_PAY = "UP_PAY_BCH_CALC";
```

### 주의 사항

변수 참조 방식은 탐지되지 않는다.

```csharp
// 탐지 안 됨 — 문자열 리터럴이 없음
private const string SP_GET = "UP_MER_INFO_GET";
conn.Execute(SP_GET, param);

// 탐지됨 — 문자열 리터럴 직접 사용
conn.Execute("UP_MER_INFO_GET", param);
```

---

## 복잡도 기준

| 등급 | CC 범위 | 의미 |
|---|---|---|
| 낮음 (Low) | 1 ~ 5 | 단순, 테스트 용이 |
| 중간 (Medium) | 6 ~ 10 | 주의 필요 |
| 높음 (High) | 11 ~ 20 | 리팩토링 권장 |
| 매우 높음 (Very High) | 21+ | 즉시 분리 필요 |

### God Class 기준

하나의 클래스에 너무 많은 책임이 집중된 경우 God Class로 분류한다.

| 항목 | 기준 |
|---|---|
| 메서드 수 | 20개 초과 |
| 총 라인 수 | 500줄 초과 |
| 평균 순환복잡도 | CC 10 초과 |

---

## 기술 스택

| 구분 | 내용 |
|---|---|
| 언어 | Python 3.11+ |
| 웹 프레임워크 | Flask 3.x (Jinja2 서버 렌더링) |
| 복잡도 분석 | Lizard 1.17.x |
| GitLab 연동 | python-gitlab 4.x |
| GitHub 연동 | PyGithub 2.x |
| Excel 생성 | openpyxl 3.x |
| 빌드 | PyInstaller 6.x |
| 시각화 | D3.js v7, Chart.js v4 (로컬 번들) |
| 스타일 | Tailwind CSS (로컬 번들) |
| 테스트 | pytest 8.x + pytest-cov |

> CDN 완전 금지 — 모든 외부 JS/CSS는 `static/` 디렉터리 로컬 번들.

---

## 디렉터리 구조

```
PGAnalyzer/
├── app.py                        # Flask 앱 팩토리 + PyInstaller 진입점
├── config.py                     # 환경 설정
├── routes/                       # Flask 블루프린트 (라우팅 전용)
│   ├── source_routes.py          # 소스 연결 API
│   ├── analyze_routes.py         # 분석 실행 API
│   ├── graph_routes.py           # 그래프 데이터 API
│   ├── search_routes.py          # 전역 검색 API
│   ├── export_routes.py          # Excel 내보내기 API
│   └── page_routes.py            # 페이지 렌더링
├── services/                     # 비즈니스 로직
│   ├── source_service.py         # GitLab/GitHub/로컬 통합 소스 관리
│   ├── gitlab_client.py          # GitLab API 어댑터
│   ├── gitlab_mock.py            # GitLab Mock (로컬 개발용)
│   ├── github_client.py          # GitHub API 어댑터
│   ├── analyze_service.py        # 분석 오케스트레이션
│   ├── search_service.py         # 전역 키워드/SP 검색
│   ├── export_service.py         # Excel 생성
│   └── result_cache.py           # 분석 결과 캐시
├── analyzers/                    # 핵심 분석 엔진 (순수 함수)
│   ├── complexity_analyzer.py    # Lizard CC 측정, God Class 탐지
│   ├── sp_detector.py            # SP 호출 패턴 탐지, Dead SP 판별
│   ├── dependency_analyzer.py    # 프로젝트 간 의존성 (.csproj 파싱)
│   └── flow_analyzer.py          # 파일/클래스 호출 흐름 파싱
├── templates/                    # Jinja2 HTML 템플릿
│   ├── base.html                 # 공통 레이아웃 (nav, sidebar)
│   ├── setup.html                # 소스 연결 설정
│   ├── dashboard.html            # 통합 대시보드
│   ├── complexity.html           # 복잡도 상세
│   ├── search.html               # 전역 검색
│   ├── dependency.html           # 의존성 흐름도
│   ├── flow.html                 # 호출 흐름도
│   └── sp_flow.html              # SP 호출 흐름도
├── static/                       # 로컬 번들 정적 파일
│   ├── js/
│   │   ├── d3.v7.min.js
│   │   ├── chart.v4.min.js
│   │   └── app.js
│   └── css/
│       └── tailwind.min.css
├── utils/                        # 공통 유틸리티
│   ├── validators.py             # 입력 검증 (URL, 경로, 키워드)
│   ├── log_filter.py             # 로그 마스킹 (token, password 등)
│   └── response_helper.py       # API 응답 포맷 헬퍼
├── tests/
│   ├── unit/                     # 단위 테스트
│   └── integration/              # 통합 테스트 (Mock GitLab/GitHub)
└── temp/                         # 프로젝트 클론 임시 폴더 (gitignore)
```

---

## API 엔드포인트

### 소스 연결

| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/api/sources/gitlab/connect` | GitLab 연결 |
| POST | `/api/sources/github/connect` | GitHub 연결 |
| POST | `/api/sources/local/validate` | 로컬 폴더 검증 |

### 분석

| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/api/analyze/start` | 분석 시작 (백그라운드) |
| GET | `/api/analyze/results` | 분석 결과 조회 |

### 그래프

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/graph/dependency` | 의존성 그래프 데이터 |
| GET | `/api/graph/flow/sp` | SP 호출 흐름 데이터 |

### 검색 / 내보내기

| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/api/search` | 전역 키워드 검색 |
| GET | `/api/export/excel` | Excel 파일 다운로드 |

---

## Excel 내보내기 시트 구성

| 시트명 | 내용 |
|---|---|
| 전체 함수 목록 | 모든 함수의 CC, 라인 수, 파일 경로 |
| 위험 함수 목록 | CC 11 이상 함수 (High / Very High) |
| God Class 목록 | God Class로 분류된 클래스 |
| SP 사용 현황 | SP명, 호출 위치, Dead SP 여부 |
| 프로젝트별 요약 | 프로젝트 단위 통계 요약 |

---

## 실행 방법

### 개발 환경 (Python)

```bash
pip install -r requirements.txt
python app.py
# → http://localhost:5000 자동 오픈
```

### 폐쇄망 환경 (.exe)

```
dist/PGAnalyzer.exe 더블클릭
→ Flask 서버 자동 시작
→ localhost:5000 브라우저 자동 오픈
```

포트 5000 사용 중이면 5001, 5002 순으로 자동 탐색.

### PyInstaller 빌드

```bash
pyinstaller --onefile --noconsole \
  --add-data "templates:templates" \
  --add-data "static:static" \
  app.py
```

---

## 테스트

```bash
# 단위 테스트
pytest tests/unit/

# 통합 테스트
pytest tests/integration/ -c pytest.integration.ini

# 커버리지 포함
pytest tests/unit/ --cov=analyzers --cov=services --cov-report=term-missing
```

### 커버리지 기준

| 항목 | 기준 |
|---|---|
| Line Coverage | 90% (BLOCKING) |
| Branch Coverage | 80% (BLOCKING) |
| 대상 | `analyzers/`, `services/` |

---

## 보안 정책

- **Access Token 메모리 보관:** GitLab/GitHub PAT는 Flask 서버 프로세스 메모리에만 보관. 파일/로그/번들 기록 금지.
- **로그 마스킹:** `token`, `access_token`, `password` 키 포함 필드 자동 마스킹.
- **경로 검증:** 로컬 폴더 경로 `os.path.abspath()` 정규화 + 허용 경로 내부 확인 (Path Traversal 방지).
- **URL 검증:** GitLab/GitHub URL은 `http`/`https` scheme만 허용.
- **쉘 실행 금지:** `subprocess` 사용 시 `shell=False` + 인자 배열 방식 필수.

---

## 환경 제약

| 항목 | 내용 |
|---|---|
| 실행 OS | Windows 10+ |
| 브라우저 | Chrome / Edge 최신 버전 |
| 개발 환경 | Python 3.11+, 외부 인터넷 가능 |
| 폐쇄망 환경 | `.exe` 실행, 외부 인터넷 차단, GitLab 내부망만 가능 |
| GitLab | 폐쇄망 사설망 전용, 로컬 개발 시 Mock으로 대체 |
| GitHub | 로컬 개발 환경 전용, 폐쇄망에서 사용 불가 |

---

## 성능 목표

| 항목 | 목표 |
|---|---|
| .cs 파일 500개 전체 분석 | 30초 이내 |
| 전역 키워드 검색 | 3초 이내 |
| 분석 API 타임아웃 | 60초 |
| 검색 API 타임아웃 | 10초 |
