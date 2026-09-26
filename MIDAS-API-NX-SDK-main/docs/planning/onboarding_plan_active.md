# `midas-nx 2.1.1` 구조엔지니어 온보딩 개편안

> 기준 버전: `midas-nx 2.1.1`  
> 작성일: 2026-08-04  
> 대상 저장소: `Dennis5882/MIDAS-API-NX-SDK`  
> 핵심 대상: Python 자동화를 처음 시작하는 구조엔지니어  
> 문서 상태: 구현 기획안 — 법무·지식재산권 검토 완료 전 공개·배포 금지

> **구현 결정 (2026-08-04)**: 법무 게이트는 예방적 조항으로 확인됨(회사 실제
> 지시 아님) — 로컬 구현은 진행, 커밋/푸시/릴리스는 매번 별도 승인.
> §2.3·§9.1이 요구하는 "문서에 `midas-nx 2.1.1` 버전 고정 표기"는 **채택하지
> 않음** — 다음 릴리스마다 stale해지는 문제(PLAN.md가 이미 겪은 것과 동일 패턴)
> 때문. 대신 버전이 필요한 곳(AI context pack 등)은 `midas_nx.__version__`을
> 코드로 확인하도록 안내.

---

## 1. 개편 목적

`midas-nx`는 MIDAS Gen NX와 Civil NX Open API를 Python에서 사용할 수 있게 하는 SDK다. 현재 기능과 개발자용 자료는 비교적 충실하지만, 구조엔지니어가 처음 접했을 때는 다음 질문에 빠르게 답하기 어렵다.

- 이 SDK로 어떤 구조설계 업무를 자동화할 수 있는가?
- Python을 잘 몰라도 시작할 수 있는가?
- AI가 작성한 코드를 그대로 실행해도 안전한가?
- 코드를 실행하면 현재 모델이 변경되는가?
- 오류가 발생했을 때 다시 실행해도 되는가?
- Gen NX와 Civil NX 중 어디에서 사용할 수 있는가?

이번 개편의 목적은 API 기능을 많이 보여주는 것이 아니라, 구조엔지니어가 자신에게 맞는 진입 경로를 선택하고 안전한 첫 작업을 성공하도록 돕는 것이다.

---

## 2. 제품 포지셔닝

### 2.1 한 문장 설명

> `midas-nx` is a Python SDK for structural engineers who are beginning MIDAS NX automation—whether they want to learn Python directly or build scripts with AI-assisted coding tools.

한국어 설명:

> `midas-nx`는 Python을 직접 배우거나 AI 코딩 도구의 도움을 받아 MIDAS NX 자동화를 시작하려는 구조엔지니어를 위한 Python SDK다.

### 2.2 프로젝트 지위 표시

문서 첫 화면과 README에 다음 내용을 명확하게 표시한다.

> 이 프로젝트는 직원 주도형 오픈소스 프로젝트이며, MIDAS IT가 공식적으로 출시하거나 기술지원하는 제품이 아니다.

공식 SDK를 대체하거나 경쟁하는 프로젝트로 표현하지 않는다. 공식 SDK 및 공식 지원 채널과의 관계는 사실에 근거해 중립적으로 설명한다.

### 2.3 버전 기준

- 문서 기준 SDK: `midas-nx 2.1.1`
- Python 요구 버전: `Python 3.12 이상`
- 설치 명령:

```bash
python -m pip install --upgrade midas-nx
```

- 문서 예제는 설치된 버전에서 실제 import 및 테스트를 통과해야 한다.
- 문서가 특정 버전에 고정된 경우 페이지 상단에 기준 버전을 표시한다.
- AI가 최신 버전에 없는 함수나 엔드포인트를 추측하지 않도록 설치 버전 확인 절차를 포함한다.

---

## 3. 핵심 사용자

두 사용자 모두 구조공학 지식은 있지만 Python 기반 API 자동화 경험이 부족하다. 진입 경로는 다르지만 같은 SDK, 같은 안전수칙, 같은 실무 Recipe를 사용한다.

### 3.1 사용자 A — Python 초보 구조엔지니어

Python을 직접 배우면서 `midas-nx`를 사용하려는 구조엔지니어다.

특징:

- 구조모델, 부재, 하중, 해석결과 같은 도메인 개념은 알고 있다.
- Python 문법, `pip`, 가상환경, import 및 오류 추적에는 익숙하지 않다.
- 예제를 조금씩 수정하면서 업무 자동화를 배우고 싶어 한다.
- 일반적인 Python 강의보다 MIDAS NX 업무에 필요한 내용부터 배우기를 원한다.

필요한 지원:

- Windows에서 Python 3.12 이상 설치하기
- 터미널을 열고 명령을 실행하는 방법
- `pip`과 가상환경의 최소 개념
- 변수, 리스트, 딕셔너리, 함수 등 예제 이해에 필요한 문법
- MAPI-Key를 코드 밖에서 안전하게 설정하는 방법
- 연결 확인, 데이터 조회, 생성 및 수정 순서
- 예제의 어떤 부분을 수정해도 되는지에 대한 표시
- 오류 메시지를 읽고 다음 행동을 결정하는 방법

첫 성공 기준:

> 문서만 보고 SDK를 설치한 뒤 Gen NX 또는 Civil NX 연결을 확인하고, 현재 모델을 변경하지 않는 읽기 전용 데이터를 조회한다.

### 3.2 사용자 B — AI 코딩 초보 구조엔지니어

Python을 잘 모르지만 ChatGPT, Codex, Claude 등의 AI 코딩 도구를 이용해 자동화 스크립트를 만들고 실행하려는 구조엔지니어다.

특징:

- 원하는 구조설계 업무와 결과는 설명할 수 있다.
- AI가 생성한 Python 코드를 세부적으로 검토하기 어렵다.
- 빠르게 결과를 얻을 수 있지만 존재하지 않는 함수, 잘못된 payload 및 파괴적 코드를 발견하기 어렵다.
- 오류 발생 후 무조건 재실행하거나 API 키를 대화에 붙여 넣을 위험이 있다.

필요한 지원:

- AI에게 제공할 공식 `midas-nx 2.1.1` context pack
- 목적·제품·모델 상태·입출력을 빠짐없이 전달하는 프롬프트
- 읽기 전용 작업부터 생성하도록 하는 프롬프트 규칙
- 생성 코드 실행 전 검토 체크리스트
- 존재하지 않는 함수와 엔드포인트를 확인하는 방법
- 삭제, 덮어쓰기, 새 프로젝트, 파일 열기 및 자동 재시도 탐지
- MAPI-Key, 모델 경로 및 고객정보를 AI에 노출하지 않는 방법
- mock → 폐기 가능한 테스트 모델 → 복사 모델 순서의 검증 절차

첫 성공 기준:

> 제공된 프롬프트로 읽기 전용 스크립트를 생성하고, 체크리스트로 검토한 다음 복사 가능한 테스트 환경에서 실행한다.

### 3.3 사용자 간 이동

두 사용자를 완전히 분리하지 않는다. AI 코딩 사용자도 코드를 반복해서 사용하면서 Python을 배우게 되며, Python 초보자도 오류 해결과 코드 확장에 AI를 사용할 수 있다.

따라서 진입 페이지는 두 개로 제공하되 다음 자산은 공통으로 관리한다.

- SDK 설치 및 연결
- 안전수칙
- 실무 Recipe
- 오류 해결
- API Reference
- 버전 및 검증 상태

---

## 4. 이번 개편에서 제외할 범위

### 4.1 Excel 및 VBA

Excel과 VBA는 핵심 온보딩에서 제외한다.

이유:

- `midas-nx`는 Python SDK이며 Excel Add-in이 아니다.
- Excel을 첫 화면에 노출하면 Python 없이 Excel에서 직접 사용할 수 있다는 오해가 생길 수 있다.
- VBA 직접 REST 호출과 Python SDK 사용은 별개의 통합 설계다.
- 아직 검증된 Excel UI, Add-in 또는 설치형 도구가 없다면 온보딩 범위가 불필요하게 커진다.

향후 실제 Excel 연동 기능이 제공될 때만 별도 통합 문서로 추가한다.

```text
docs/integrations/excel.md
```

현재 단계에서는 README, 시작 경로, P0 작업 및 완료 기준에 Excel/VBA를 포함하지 않는다.

### 4.2 기타 비목표

- Python 전체 문법을 가르치는 범용 강좌
- 모든 엔드포인트를 초보자 페이지에 한 번에 노출
- GUI 애플리케이션 또는 Excel Add-in 개발
- 회사의 공식 지원을 암시하는 표현
- 검증되지 않은 생성·수정·삭제 예제를 초보자에게 제공
- 법무 검토 전 GitHub push, 신규 Release 또는 PyPI 배포

---

## 5. 온보딩 사용자 흐름

```text
처음 방문
    │
    ├─ Python을 배우면서 시작
    │      └─ 설치 → 최소 Python → 연결 → 첫 조회 → Recipe
    │
    └─ AI와 함께 시작
           └─ 안전수칙 → Context Pack → Prompt → 코드 검토 → 첫 조회
                         │
                         ▼
                   공통 안전 가이드
                         │
                         ▼
                   실무 자동화 Recipe
```

### 5.1 첫 화면에서 답해야 할 내용

사용자는 첫 화면 1분 안에 다음을 이해할 수 있어야 한다.

1. `midas-nx`가 무엇인지
2. Gen NX와 Civil NX용 Python SDK라는 점
3. 공식 MIDAS IT 제품이 아니라는 점
4. Python 3.12 이상이 필요하다는 점
5. 자신이 선택할 수 있는 두 가지 시작 경로
6. 첫 예제는 모델을 변경하지 않는다는 점

### 5.2 경로 선택 문구

> How would you like to start?

- **Learn Python and use the SDK**  
  Python을 직접 배우면서 단계별 예제를 실행한다.

- **Build a script with AI assistance**  
  검증된 context와 prompt를 사용해 AI와 안전하게 코드를 만든다.

---

## 6. 권장 문서 구조

```text
docs/
├─ index.md
├─ start-here/
│  ├─ choose-your-path.md
│  ├─ before-you-start.md
│  └─ project-status.md
├─ python-beginner/
│  ├─ windows-install.md
│  ├─ minimal-python.md
│  ├─ install-sdk.md
│  ├─ connect-to-nx.md
│  ├─ first-read.md
│  ├─ first-change.md
│  └─ troubleshooting.md
├─ ai-coding/
│  ├─ safe-start.md
│  ├─ context-pack.md
│  ├─ prompt-templates.md
│  ├─ review-checklist.md
│  ├─ error-follow-up.md
│  └─ verified-examples.md
├─ recipes/
│  ├─ index.md
│  ├─ inspect-project.md
│  ├─ read-nodes.md
│  ├─ read-elements.md
│  ├─ create-nodes.md
│  ├─ create-elements.md
│  ├─ assign-loads.md
│  └─ get-results.md
├─ safety/
│  ├─ overview.md
│  ├─ operation-levels.md
│  ├─ destructive-operations.md
│  ├─ timeout-and-retry.md
│  ├─ files-and-projects.md
│  └─ secrets-and-privacy.md
├─ reference/
│  ├─ client.md
│  ├─ db-resources.md
│  ├─ operation-functions.md
│  ├─ view-functions.md
│  └─ exceptions.md
└─ project/
   ├─ verification.md
   ├─ supported-products.md
   ├─ known-limitations.md
   ├─ contributing.md
   └─ security.md
```

기존 URL을 변경할 경우 가능한 범위에서 redirect를 제공하고 내부 링크 검사를 자동화한다.

---

## 7. 공통 Quick Start 설계

### 7.1 첫 예제 원칙

첫 예제는 반드시 다음 조건을 만족해야 한다.

- 모델을 생성하거나 수정하지 않는다.
- 파일을 열거나 교체하지 않는다.
- 분석을 실행하지 않는다.
- 전체 삭제 함수를 호출하지 않는다.
- 현재 제품과 연결 상태를 확인한다.
- 작은 범위의 데이터를 읽고 결과를 설명한다.
- 실패했을 때 모델에 영향이 없는지 명시한다.

### 7.2 권장 순서

1. Python 버전 확인
2. 가상환경 생성 및 활성화
3. `midas-nx 2.1.1` 설치
4. SDK 버전 확인
5. Gen NX 또는 Civil NX 실행
6. MAPI-Key를 환경변수로 설정
7. 연결 확인
8. 노드 또는 프로젝트 정보 읽기
9. 예상 출력 확인
10. 자주 발생하는 연결 오류 해결

### 7.3 코드 예제 요구사항

- 패키지 2.1.1에서 실제 실행되는 import만 사용한다.
- API 키를 코드에 하드코딩하지 않는다.
- 제품 선택을 명시한다.
- 실행 전 작업의 위험 등급을 출력한다.
- 예외를 사용자 언어로 설명한다.
- 응답 전체를 무조건 출력해 민감정보를 노출하지 않는다.
- 문서 빌드 과정에서 import 또는 smoke test를 수행한다.

### 7.4 첫 변경 예제

읽기 전용 예제를 완료한 다음에만 제공한다.

- 원본이 아닌 폐기 가능한 테스트 모델을 사용한다.
- 추가할 데이터와 대상 ID를 실행 전에 표시한다.
- 기존 ID 충돌을 확인한다.
- 변경 후 다시 조회해 반영 여부를 검증한다.
- timeout 후 자동 재시도하지 않는다.
- 가능한 경우 원상복구 절차를 함께 제공한다.

---

## 8. Python 초보자 경로

### 8.1 최소 Python 범위

구조엔지니어가 SDK 예제를 이해하는 데 필요한 내용만 설명한다.

- 문자열과 숫자
- 리스트와 딕셔너리
- 변수
- 함수 호출과 인자
- `import`
- `if` 문
- `for` 문
- `try/except`
- 파일과 환경변수의 개념

클래스 설계, 데코레이터, 비동기 프로그래밍 등은 첫 온보딩에서 제외한다.

### 8.2 예제 설명 방식

각 코드 블록 다음에 다음 정보를 표시한다.

- 이 코드가 하는 일
- 사용자가 바꿔야 하는 값
- 바꾸면 안 되는 부분
- 모델 변경 여부
- 정상 출력 예시
- 실패 시 확인할 항목
- 다음 학습 문서

### 8.3 성공 단계

```text
Level 1: 설치와 연결 확인
Level 2: 모델 데이터 읽기
Level 3: 읽은 데이터 필터링하기
Level 4: 테스트 모델에 데이터 하나 추가하기
Level 5: 구조설계 업무 Recipe 수정하기
```

---

## 9. AI 코딩 초보자 경로

### 9.1 AI Context Pack

AI에게 한 번에 전달할 수 있는 짧은 공식 문서를 제공한다. 다음 내용을 포함한다.

- 패키지명과 기준 버전: `midas-nx 2.1.1`
- Python 요구 버전: `3.12 이상`
- 지원 제품과 제품 선택 방법
- 실제 공개 API와 주요 import 경로
- 응답 및 예외 처리 원칙
- 안전 등급
- 금지 작업
- 테스트 순서
- 공식 문서 및 API Reference 링크
- 존재하지 않는 함수나 endpoint를 추측하지 말라는 규칙

Context Pack은 SDK 릴리스와 함께 테스트하고 버전별로 보관한다.

### 9.2 기본 프롬프트 구조

```markdown
You are helping a structural engineer use midas-nx 2.1.1 with Python 3.12+.

Product: Gen NX or Civil NX
Current model state: [describe without confidential information]
Goal: [one concrete task]
Inputs: [IDs, load cases, units, selections]
Expected output: [screen output, JSON summary, or file]

Requirements:
1. Use only functions confirmed in the installed midas-nx 2.1.1 documentation.
2. Start with a read-only version of the workflow.
3. Do not use delete_all, project replacement, file overwrite, or automatic retries.
4. Read the MAPI-Key from an environment variable; never print it.
5. Before any write, print a preview of the target, IDs, and intended changes.
6. Explain whether each API call reads, creates, modifies, or deletes data.
7. If an API call times out, stop and ask the user to verify the model state.
8. Provide a pre-run safety checklist and an expected output example.
```

### 9.3 생성 코드 검토 체크리스트

실행 전에 다음 항목을 확인한다.

- [ ] 패키지 버전이 2.1.1 기준인가?
- [ ] 실제 문서에 존재하는 import와 함수인가?
- [ ] Gen NX와 Civil NX 선택이 올바른가?
- [ ] 첫 실행이 읽기 전용인가?
- [ ] MAPI-Key가 코드, prompt 또는 로그에 포함되지 않았는가?
- [ ] `delete_all` 또는 전체 범위 DELETE가 없는가?
- [ ] 새 프로젝트, 프로젝트 열기, 파일 덮어쓰기가 없는가?
- [ ] timeout 후 자동 재시도 로직이 없는가?
- [ ] 쓰기 작업 전에 대상 ID와 변경 내용을 보여주는가?
- [ ] 원본이 아닌 테스트 또는 복사 모델을 사용하는가?
- [ ] 실행 후 조회를 통해 실제 반영 여부를 확인하는가?

### 9.4 AI 오류 후속 프롬프트

오류를 AI에게 전달할 때 API 키, 고객명, 모델 경로 및 원본 모델 데이터를 제거한다. 다음 형식을 제공한다.

```markdown
Installed midas-nx version:
Python version:
Product: Gen NX / Civil NX
Operation type: read / create / update / delete
What I expected:
What happened:
Sanitized error message:
Could the request have been applied despite the error?: unknown

Do not suggest an automatic retry. First explain how to verify the current model state safely.
```

---

## 10. 안전 등급

모든 문서와 Recipe 상단에 위험 등급을 표시한다.

| 등급 | 의미 | 예시 |
|---|---|---|
| Level 0 | 연결·로컬 검사 | 버전 확인, 연결 확인 |
| Level 1 | 읽기 전용 | 노드, 요소, 상태 조회 |
| Level 2 | 제한적 추가 | 테스트 모델에 신규 항목 추가 |
| Level 3 | 기존 데이터 수정 | 재료·단면·하중 수정 |
| Level 4 | 고위험 | 삭제, 전체 삭제, 파일 열기·교체, 새 프로젝트 |

Level 3 이상은 다음을 필수로 한다.

- 복사 모델 사용
- 변경 대상 preview
- 명시적 사용자 확인
- 실행 후 검증 조회
- timeout 시 중단
- 복구 또는 수동 확인 절차

초보자 Quick Start에서는 Level 0과 Level 1만 사용한다.

---

## 11. 실무 Recipe 표준

```markdown
# [구조설계 업무 이름]

- 대상: Python 초보 / AI 코딩 초보 / 공통
- 기준 SDK: midas-nx 2.1.1
- 지원 제품: Gen NX / Civil NX / 둘 다
- 위험 등급: Level 0–4
- 예상 시간:
- 사전 조건:
- 모델 변경 여부:
- 실제 제품 검증 상태:

## 이 작업으로 얻는 결과
## 실행 전 체크리스트
## 입력값
## 전체 코드
## 코드 설명
## 예상 출력
## 결과 검증
## 자주 발생하는 오류
## timeout 및 재실행 판단
## 복구 방법
## 관련 API Reference
## AI에게 수정 요청하는 프롬프트
```

Recipe는 중간 코드 조각이 아니라 처음부터 끝까지 실행할 수 있는 형태로 제공한다. 제품별 차이가 있으면 코드 내부의 추측으로 처리하지 말고 문서에서 명시적으로 분기한다.

---

## 12. 오류 안내 원칙

HTTP 상태코드만 설명하지 말고 사용자가 겪는 증상 중심으로 구성한다.

주요 항목:

- Python 명령을 찾을 수 없음
- Python 버전이 3.12 미만임
- `midas_nx`를 import할 수 없음
- MIDAS NX와 연결되지 않음
- MAPI-Key가 없거나 잘못됨
- Gen NX/Civil NX 제품 선택이 잘못됨
- 프로젝트가 열려 있지 않음
- endpoint 또는 payload가 현재 제품에서 지원되지 않음
- 요청이 timeout됨
- 실패 응답을 받았지만 모델 반영 여부가 불분명함
- AI가 존재하지 않는 함수를 생성함

각 오류 페이지는 다음 순서로 작성한다.

1. 사용자가 보는 증상
2. 모델이 변경됐을 가능성
3. 지금 해야 할 안전한 확인
4. 재실행해도 되는지 여부
5. 기술적 원인
6. 해결되지 않을 때 문의할 곳

---

## 13. API Reference 개선

각 API 항목에 다음 정보를 표시한다.

| 항목 | 내용 |
|---|---|
| 사용자 기능명 | 구조엔지니어가 이해할 수 있는 업무 이름 |
| Python 위치 | 실제 import 경로와 함수·클래스명 |
| 원본 endpoint | HTTP method와 경로 |
| 지원 제품 | Gen NX / Civil NX |
| 작업 유형 | read / create / update / delete |
| 위험 등급 | Level 0–4 |
| 검증 상태 | mock / live-read / live-write / 미검증 |
| 입력 형식 | 필수 필드와 예제 |
| 주의사항 | 제품 차이, timeout, 기존 알려진 문제 |
| 관련 Recipe | 초보자가 실행할 수 있는 업무 예제 |

SDK가 endpoint를 구현했다는 사실과 실제 제품에서 안전하게 검증됐다는 사실을 구분한다.

---

## 14. 구현 단계

### Phase 0 — 공개 및 권리 검토 게이트

구현과 내부 검토는 가능하지만 다음 승인이 끝나기 전 공개 배포는 진행하지 않는다.

- 회사 소스코드 또는 비공개 문서 포함 여부
- `MIDAS-API`에서 가져온 문서·예제·스키마의 이용 권한
- 업무상저작물 및 개인 저작권 귀속
- MIDAS, Gen NX, Civil NX 명칭 사용
- MIT 라이선스 배포 권한
- 고객 모델과 실제 제품 검증 기록의 공개 가능 범위

금지 작업:

- GitHub push
- 신규 GitHub Release
- PyPI 신규 배포
- LinkedIn 또는 외부 홍보

### Phase 1 — 문서 조사와 테스트 기준 고정

- README, Quick Start, safety, examples 및 reference 목록 작성
- 2.1.1의 실제 공개 API와 import 경로 추출
- 오래된 버전 및 깨진 링크 탐지
- 현재 문서에서 Excel/VBA 경로 식별
- 재사용, 이동, 삭제 및 새 작성 항목 구분
- 예제별 위험 등급과 검증 상태 기록

산출물:

- 현재 문서 지도
- 콘텐츠 이동표
- 2.1.1 공개 API 목록
- 예제 테스트 목록
- 삭제할 Excel/VBA 온보딩 항목

### Phase 2 — 첫 화면과 두 진입 경로

- 프로젝트 설명과 비공식 지위 표시
- Python 3.12+ 및 SDK 2.1.1 요구사항 표시
- 두 사용자 경로 선택 UI
- 첫 코드를 읽기 전용으로 교체
- Python 초보자 Quick Start 작성
- AI 코딩 안전 시작 문서 작성

### Phase 3 — 공통 안전 기반

- 위험 등급 적용
- 파괴적 작업 문서화
- timeout 및 재시도 정책 작성
- API 키와 개인정보 보호 지침 작성
- 첫 변경 예제에 preview와 검증 절차 적용

### Phase 4 — Recipe와 오류 문서

- 자주 사용하는 구조설계 업무를 Recipe로 전환
- AI용 prompt를 각 Recipe에 추가
- 증상 중심 troubleshooting 작성
- Gen NX와 Civil NX 차이를 명시

### Phase 5 — Reference와 자동 검증

- 전체 공개 API Reference 생성
- 문서 예제 import test
- Quick Start smoke test
- 내부 링크 검사
- SDK 버전 자동 표시
- 비밀정보 탐지
- 문서와 coverage ledger의 불일치 검사

---

## 15. 우선순위

### P0 — 반드시 먼저

- 법무·지식재산권 공개 승인 게이트
- README의 버전을 2.1.1 기준으로 통일
- Python 3.12+ 요구사항 명시
- Excel/VBA 핵심 온보딩 제거
- 두 구조엔지니어 사용자 경로 생성
- 읽기 전용 첫 예제
- Windows 설치·연결·첫 조회 문서
- AI Context Pack
- 안전한 기본 프롬프트
- 실행 전 코드 검토 체크리스트
- 프로젝트 지위 및 지원 범위 표시

### P1 — P0 이후

- 최소 Python 문서
- 공통 위험 등급
- 첫 변경 예제
- 구조설계 Recipe 표준화
- 증상 중심 troubleshooting
- AI 오류 후속 프롬프트
- 문서 예제 자동 테스트

### P2 — 사용자 검증 이후

- Reference 자동 생성
- 지원 제품 및 검증 상태 필터
- 명령행 진단 도구 검토
- preview 또는 dry-run 보조 기능 검토
- 사용자 피드백 기반 Recipe 확장

---

## 16. 테스트 계획

### 16.1 자동 검사

- `mkdocs build --strict`
- README 및 Quick Start 코드 import test
- Python 3.12과 지원 버전 테스트
- `midas-nx 2.1.1` 설치 smoke test
- 내부 링크와 anchor 검사
- 문서에 2.0.0 등 오래된 기준 버전이 남아 있는지 검사
- MAPI-Key 및 민감정보 패턴 검사
- 위험 작업 키워드 검사
- AI Context Pack의 import 및 함수명 검사

### 16.2 사용자 테스트

각 그룹의 구조엔지니어 최소 2명에게 추가 설명 없이 문서만 제공한다.

공통 과제:

1. 프로젝트의 용도와 지위를 설명한다.
2. 자신의 시작 경로를 선택한다.
3. Python과 SDK를 설치한다.
4. Gen NX 또는 Civil NX에 연결한다.
5. 읽기 전용 데이터를 조회한다.
6. timeout 상황에서 무조건 재실행하지 않고 상태를 확인한다.
7. 위험한 작업을 구분한다.

Python 초보자 추가 과제:

- 예제에서 제품과 조회 대상을 안전하게 변경한다.
- 간단한 리스트 또는 딕셔너리 값을 수정한다.
- 오류 메시지를 보고 올바른 troubleshooting 문서로 이동한다.

AI 코딩 초보자 추가 과제:

- Context Pack과 prompt로 읽기 전용 코드를 생성한다.
- 체크리스트에서 위험 요소를 찾아낸다.
- 삭제 또는 자동 재시도가 포함된 코드의 실행을 중단한다.
- 민감정보를 제거한 오류 후속 prompt를 작성한다.

측정 항목:

- 첫 성공까지 걸린 시간
- 진행이 막힌 단계
- 잘못 이해한 용어
- 외부 도움 요청 횟수
- 위험 코드를 탐지한 비율
- 성공 후 다음 Recipe로 이동한 비율

---

## 17. 완료 기준

다음 조건을 모두 만족하면 온보딩 개편이 완료된 것으로 본다.

- 첫 화면에서 SDK 용도, 대상 제품, 비공식 지위 및 요구 Python 버전을 이해할 수 있다.
- Excel/VBA가 핵심 사용자 경로와 P0 문서에서 제거되어 있다.
- 두 구조엔지니어 사용자 유형을 한 번의 선택으로 구분할 수 있다.
- Python 초보자가 문서만 보고 30분 안에 설치, 연결 및 첫 조회를 완료한다.
- AI 코딩 초보자가 공식 Context Pack과 prompt를 사용한다.
- 첫 예제는 모델을 변경하지 않는다.
- 모든 Recipe에 SDK 버전, 제품, 위험 등급 및 검증 상태가 표시된다.
- AI 사용자는 생성 코드가 검증된 코드가 아님을 이해한다.
- timeout 이후 무조건 재실행하지 않도록 안내한다.
- API 키가 코드, 문서 출력, 로그 및 테스트 산출물에 포함되지 않는다.
- 문서 코드와 링크가 CI에서 검증된다.
- 공개 전 회사의 법무·지식재산권 검토가 완료된다.

---

## 18. AI 구현 요청문

아래 요청문을 저장소를 수정할 AI에게 전달한다.

```markdown
# Task: Redesign the midas-nx onboarding for beginner structural engineers

Target SDK: midas-nx 2.1.1
Required Python: 3.12+

The onboarding must support two primary audiences:

1. Structural engineers who are new to Python and want to learn while using the SDK.
2. Structural engineers who know little Python and use ChatGPT, Codex, Claude, or similar AI coding tools to create and run scripts.

Scope rules:

- Remove Excel and VBA from the core onboarding, navigation, P0 scope, and acceptance criteria.
- Do not build an Excel add-in, VBA bridge, or GUI.
- Present midas-nx as an employee-led open-source project, not an officially released or supported MIDAS IT product.
- Do not position it as a replacement for the official SDK.
- Make the first executable example strictly read-only.
- Do not use project creation, project opening, file overwrite, delete_all, bulk deletion, analysis execution, or automatic retry in the first tutorial.
- Read the MAPI-Key from an environment variable and never print it.
- Use only imports, classes, functions, and endpoints verified against the installed midas-nx 2.1.1 package.
- Clearly distinguish implementation coverage from live product verification.
- Add a safety level, supported product, model-change status, and verification status to every recipe.
- Add a versioned AI context pack, safe prompt templates, a generated-code review checklist, and a sanitized error follow-up template.
- Keep shared SDK logic, safety guidance, recipes, and troubleshooting common to both user paths.
- Preserve existing URLs where practical and provide redirects when documents move.
- Do not push, publish a release, upload to PyPI, or promote the project. Legal and IP review is still pending.

Before editing:

1. Audit README, MkDocs navigation, quick starts, safety docs, examples, references, and coverage data.
2. Create a current-document map and identify content to reuse, move, rewrite, or remove.
3. Verify the public API and import paths from the installed midas-nx 2.1.1 package.
4. Identify all Excel/VBA onboarding references.
5. Identify examples that create, update, delete, replace files, open projects, run analysis, or retry requests.
6. Report any source-provenance, confidential-information, trademark, or licensing concern without attempting to hide or delete evidence.

Implementation order:

1. Update project positioning and version requirements.
2. Create the two-path start page.
3. Implement the Python beginner read-only quick start.
4. Implement the AI coding safe-start path and context pack.
5. Add shared safety levels and troubleshooting.
6. Standardize recipes.
7. Improve the API reference and automated documentation tests.

Validation:

- Run the existing test suite, Ruff, mypy, wheel install smoke test, and MkDocs strict build.
- Test all onboarding imports against midas-nx 2.1.1 on Python 3.12+.
- Check internal links and stale version references.
- Scan docs, examples, logs, and generated files for API keys and sensitive information.
- Confirm that the first tutorial cannot modify the active MIDAS NX model.

For the first response, do not edit files. Report:

- the current onboarding weaknesses;
- the proposed document map;
- reusable and removable content;
- the exact P0 file changes;
- compatibility or URL risks;
- legal/IP or confidential-information concerns that require human approval.
```

---

## 19. 최종 방향

이번 개편의 목표는 문서를 많이 만드는 것이 아니다. 구조엔지니어가 다음 두 질문에 즉시 답할 수 있도록 만드는 것이다.

1. 나는 Python을 배우면서 시작할 것인가?
2. 나는 AI의 도움을 받아 시작할 것인가?

어느 경로를 선택하더라도 첫 경험은 읽기 전용이고, 같은 안전 기준과 검증된 SDK 기능을 사용해야 한다. Excel/VBA는 실제 통합 제품이 준비되기 전까지 핵심 온보딩에서 제외한다.
