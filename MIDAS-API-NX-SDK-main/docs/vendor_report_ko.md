# MIDAS NX Open API — 이슈 리포트 (2026-07-29 최초, v1.4 — 2026-09-21 갱신)

`/db/*` 43개 엔드포인트에 대해 생성 → 조회 → 수정 → 삭제 왕복을 수행했고, 42개는 정상
동작을 확인했습니다. 아래는 정상 동작하지 않은 항목입니다.

**v1.4 기준 검증 범위**: 그 이후로 같은 방식의 왕복 검증을 172개 엔드포인트(183개 케이스)로
넓혔고, 그중 아래 항목만이 미해결로 남아 있습니다. 나머지는 모두 문서대로 동작했거나,
저희 쪽 호출 오류로 확인돼 철회했습니다(부록 참조).

담당 부서가 다를 것으로 보아 **제품 결함(A)과 문서 관련(B)을 분리**했습니다. B는 발송 전
공식 온라인 매뉴얼 원문(2026-07-27 기준)과 다시 대조했습니다.

| 항목 | 내용 |
| --- | --- |
| 제품 | MIDAS CIVIL NX 2026 및 MIDAS GEN NX 2026 (항목별 확인 제품은 각 절에 명기) |
| 버전 | **2026-09-21에 두 제품(Gen NX 2026 v2.1, Civil NX 2026 v2.2)에서 A-2·A-3·A-4·A-6·A-7·A-8·A-9·A-10을 일괄 재확인**했습니다. 그날 `/info` 전수 스캔 결과가 Build 09/15/2026 기준 스냅샷과 일치합니다 |
| 재확인 안 된 항목 | A-5 한 건입니다. 제품을 강제 종료해야 재현되는 형태라 2026-07이 마지막 측정이며, 모달 대기 중에 같은 현상이 나오는 것은 2026-09-21에 확인했습니다(A-7 참조) |
| 릴레이 | `https://moa-engineers.midasit.com:443/civil`, `.../gen` |
| 클라이언트 | Python 3.13 + `requests` (SDK 미사용) |

| # | 대상 | 내용 | 심각도 |
| --- | --- | --- | --- |
| A-2 | `DELETE /db/*` | 문서화된 형식이 지정 ID를 무시하고 **테이블 전체를 삭제** | 치명적 |
| A-3 | 10개 엔드포인트 | 쓰기가 무시·변조됐는데 **응답은 성공** (v1.4에서 7건 추가) | 높음 |
| A-4 | 전역 | 오류 본문이 HTTP **200 / 201**로 반환 | 중간 |
| A-5 | `/mapikey/verify` | 프로그램 종료 후 일정 시간 `"connected"` 반환 | 중간 |
| A-6 | 오류 메시지 | `"Wrong Field"`가 실제로는 **값** 오류를 의미 | 중간 |
| A-7 | `/doc/SAVEAS` | 쓸 수 없는 경로로 저장 시 **Civil은 성공 메시지를 반환하고 파일을 만들지 않으며, Gen은 응답 없이 세션이 차단**됨 | 높음 |
| A-8 | `/info` | `/DESIGN/*` 전 계열(147쌍)과 Hyper-S `IEHG` 3종에 스키마가 제공되지 않음 | 중간 |
| A-9 | `/info` | 제품 자신의 스키마가 실제 수용 필드와 **양방향으로** 어긋남 | 중간 |
| A-10 | 9개 엔드포인트 + `/db/RPSC` | 문서화된 형태로 쓰기가 되지 않음 — **결함 주장이 아닌 동작 예시 요청** | — |
| B-1~3 | 매뉴얼 | 기본값·예시·키 처리에 대한 보완 요청 | — |
| B-4 | `/db/REBW` | **필드명 전체가 실제 서버 스키마와 다름** (매뉴얼만의 문제, 서버는 정상·일관 동작) | 높음 |
| B-5 | `/db/REBC` | `Active Methods`와 주철근 필드 구조가 실제 서버 스키마와 다름 | 높음 |

재현 코드는 `requests`만 사용합니다. 공통 헬퍼:

```python
import requests
BASE = "https://moa-engineers.midasit.com:443/civil"
H = {"Content-Type": "application/json", "MAPI-Key": "<MAPI Key>"}

def call(method, endpoint, body=None, timeout=15):
    r = requests.request(method, BASE + endpoint, headers=H, json=body, timeout=timeout)
    return r.status_code, r.json()
```

---

# A. 제품 결함

## A-2. 🛑 `DELETE {endpoint}` + ID 지정 `"Assign"`이 테이블 전체를 삭제합니다

매뉴얼 기재 형식대로 호출했을 때 발생하며, 지정한 ID가 무시됩니다.

| 요청 | 결과 |
| --- | --- |
| `DELETE /db/NODE` + `{"Assign": {"21": null}}` | **NODE 10개 → 0개, ELEM 4개 → 0개** |
| `DELETE /db/NODE` + `{"Assign": {"3": {}}}` | 테이블 전체 삭제 |
| `DELETE /db/STLD` + `{"Assign": {"1": {}}}` | 하중조건 2개 모두 삭제 |
| **`DELETE /db/NODE/502`** | **502만 삭제** (기대 동작, 문서에 없음) |

**2026-09-21 재확인 — 두 제품, 같은 세션, 같은 모델에서 두 호출 차이입니다.**
폐기용 더미 모델(절점 10·요소 4·하중조건 2)을 만들어 순서대로 호출했습니다.

| 호출 | 이전 | 이후 |
| --- | --- | --- |
| `DELETE /db/NODE/6` (문서에 없는 per-id 형식) | NODE 10, ELEM 4 | NODE 9, ELEM 3 |
| `DELETE /db/STLD` + `{"Assign": {"1": {}}}` | STLD 2 | **STLD 0** |
| `DELETE /db/NODE` + `{"Assign": {"3": {}}}` | NODE 9, ELEM 3 | **NODE 0, ELEM 0** |

per-id 형식은 정확히 의도대로 동작합니다 — 절점 6과 그에 붙은 요소 하나만 사라집니다.
문서화된 형식은 지정한 ID를 무시하고 테이블을 비우며, `/db/NODE`에서는 **한 번의 호출로
모델 전체**가 사라집니다. 두 제품 동일합니다.

`/db/NODE`는 삭제된 절점에 연결된 요소까지 사라지므로 **단일 호출로 모델이 소실됩니다.**
`/db/NODE`·`/db/STLD`·`/db/LDGR`·`/db/MATL`에서 동일하게 확인했습니다.

응답 본문이 삭제된 **모든** 레코드를 반환하므로 응답을 보면 과다 삭제를 알 수는 있으나,
이미 삭제된 뒤입니다. 문서를 per-ID 형식으로 고치시든 본문 형식이 ID를 존중하도록
고치시든, 현재는 문서를 따라 구현하면 모델이 소실되는 조합입니다.

## A-3. ⚠️ 쓰기가 무시·변조됐는데 응답은 성공을 반환합니다

개별 사안이 아니라 하나의 유형으로 보고 있습니다. 호출 측에서 알아차릴 방법이 레코드를
다시 읽어 비교하는 것뿐입니다.

| 대상 | 입력 | 실제 결과 | 응답 |
| --- | --- | --- | --- |
| `/db/CONS` | `CONSTRAINT` 8자 | 앞 7자로 **절단** → 요청하지 않은 구속 생성 | 200. **응답은 8자 그대로 반환** |
| `/db/MVHL` | `VEHICLE_TYPE_NAME: "NOT-A-VEHICLE"` | 존재하지 않는 표준 차량명이 **그대로 저장** | 200, 오류 없음 |
| `/db/SECF` | 단면이 없는 키(element ID) 사용 | **아무것도 저장되지 않음** | 200. **응답은 레코드 전체를 그대로 반환** |
| `/db/MATD` (Civil) | `bSERVCHECK`·`dSHORTTERM`·`dLONGTERM` PUT | **세 필드 모두 저장되지 않음** | 200. **응답은 요청값을 그대로 반환** |
| `/db/SPLC` (Gen) | `aACCECC_ECCEN_LIST[0].ALONG` 2.5 → 3.5 PUT | **기존값 2.5 유지** | 200. **응답은 3.5를 반환** |
| `/db/SSEIS` (Gen) | 오타 키 `IINHERENT_TORSION`·`NHERENT_TORSION` | 무시되고 `INHERENT_TORSION`은 `false` 유지 | 201, 오류 없음 |
| `/db/STCT` (양 제품) | `iITER`·`TOL` | **두 필드만 누락**, 나머지 12개 필드는 정상 저장 | 200/201. **응답은 요청값을 그대로 반환** |
| `/db/SBDO`·`/db/SINF`·`/db/MVLDpl` (양 제품) | 빈 테이블에 id `1` POST | **레코드가 생성되지 않음** | 201, 오류 없음 |

```python
# /db/CONS — 응답도 절단 사실을 알려주지 않습니다
call("POST", "/db/CONS", {"Assign": {"3": {"ITEMS": [{"ID": 1, "CONSTRAINT": "11111111"}]}}})
# 응답: {"CONS": {"3": {"ITEMS": [{"ID": 1, "CONSTRAINT": "11111111"}]}}}   8자
call("GET", "/db/CONS")
# 저장: {"3": {"ITEMS": [{"ID": 1, "CONSTRAINT": "1111111"}]}}              7자
```

6자는 오류로 정상 거부됩니다(`[Error] Constraint Condition has(have) been incorrectly
entered.`). **짧으면 거부하고 길면 조용히 잘라내는 비대칭**이 문제로 보입니다.

```python
# /db/MVHL — 존재하지 않는 표준 차량명
call("POST", "/db/MVHL", {"Assign": {"1": {
    "MVLD_CODE": 2, "VEHICLE_LOAD_NAME": "NONSENSETYPE", "VEHICLE_LOAD_NUM": 1,
    "VEHICLE_TYPE_NAME": "NOT-A-VEHICLE", "STANDARD_CODE": "AASHTO-LRFD",
    "VEH_DEFAULT": {"DYN_LOAD_ALLOWANCE": 33, "CENT_F": False}}}})
# 저장: {..., "VEHICLE_TYPE_NAME": "NOT-A-VEHICLE", ...}   그대로 저장됩니다.
```

`STANDARD_CODE`는 자체 enum 검증을 받아 `"NOT-A-CODE"`는 `Wrong Field`로 거부되지만,
`VEHICLE_TYPE_NAME`은 검증되지 않습니다. 이 이름이 어떤 표준 차량의 축하중을 쓸지를
결정하므로, 오타 하나가 해석 결과를 조용히 바꿉니다. 같은 요청에서 `STANDARD_CODE`에
AASHTO LRFD 차량과 한국 기준(`"KS-RB"`)을 함께 보내도 그대로 저장됩니다.

> 보고서 이전 판에서는 이 자리에 `VEHICLE_LOAD_NUM: 2`가 표준 차량을 조용히
> 사용자정의 차량으로 바꿈다고 적어 두었습니다. **철회합니다** — 2026-09-03 재측정 결과
> `VEHICLE_LOAD_NUM`은 분기 선택자이고(`1`=표준, `2`=사용자정의), `2`를 보낸 뒤
> 표준 차량 필드가 무시되는 것은 문서대로 동작한 것입니다. 제품 결함이 아닙니다.

`/db/SECF`는 **단면 ID**를 키로 받습니다. 단면이 없는 번호를 키로 보내면 200이
반환되면서 아무것도 저장되지 않습니다. 잘못된 키를 쓴 호출자 쪽 실수였지만, **응답이
저장되지 않은 레코드를 그대로 되돌려 줍니다** — `/db/CONS`·`/db/MATD`와 같은 서명입니다.
2026-09-21 재확인: 키 `4`(요소 번호, 해당 단면 없음)으로 POST하면 응답은
`{"SECF": {"4": {"ITEMS": [...]}}}`이고 이어진 `GET /db/SECF`는 `{"message": ""}`입니다.

### v1.4 추가 (1) — 2026-09-18 측정, 두 제품 Build 09/15/2026

모두 **빈 스크래치 문서에서 문서화된 선행 조건을 만든 뒤**, HTTP 상태가 아니라 쓰기
직후의 GET으로 판정했습니다. 세 건 모두 응답만 보면 성공과 구분되지 않습니다.

**`/db/MATD` — Civil에서만 세 필드가 반영되지 않습니다.** `bSERVCHECK: true`,
`dSHORTTERM: 1.25`, `dLONGTERM: 1.5`를 각각 따로, 그리고 한 번에 PUT했습니다.

| 제품 | PUT 응답 | 직후 GET |
| --- | --- | --- |
| Gen NX | 요청값 그대로 | 세 필드 모두 반영 (`true` / `1.25` / `1.5`) |
| Civil NX | 요청값 그대로 | **세 필드가 레코드에 존재하지 않음** |

같은 요청, 같은 빌드에서 제품에 따라 결과가 갈립니다. Civil에서 이 세 필드가 지원되지
않는 것이라면 응답에 요청값을 되돌려 주는 대신 거부하는 편이 호출자가 알 수 있습니다.

**`/db/SPLC` — 생성은 되는데 수정이 조용히 무시됩니다.** Gen NX에서
`aACCECC_ECCEN_LIST[0].ALONG`을 `2.5`로 POST하면 GET에도 `2.5`로 저장됩니다. 이어서
같은 필드를 `3.5`로 PUT하면 응답은 `3.5`를 반환하지만, GET은 계속 `2.5`를 돌려줍니다.
**생성 경로는 이 필드를 쓰고 수정 경로는 쓰지 않는 것**으로 보입니다. 값이 반영되지
않았다는 사실이 응답 어디에도 나타나지 않습니다.

**`/db/SSEIS` — 인식되지 않는 키가 201과 함께 사라집니다.** 오타 키
`IINHERENT_TORSION`/`NHERENT_TORSION`으로 `true`를 보내면 HTTP 201이 반환되고 응답
본문에서는 해당 키가 그대로 사라지며, GET은 실제 필드 `INHERENT_TORSION`을 `false`로
유지합니다. 위 두 건보다 가벼운 사안이지만 같은 유형입니다 — **인식하지 못한 키를 받은
사실이 호출자에게 전달되지 않습니다.** 공식 아티클 본문에 이 두 철자가 등장하므로,
문서를 복사해 붙여넣은 호출은 설정이 적용되지 않은 채 성공으로 보입니다.

### v1.4 추가 (2) — 누락되는 필드와 생성되지 않는 레코드

앞서의 항목들과 같은 유형이며, 다만 이 네 건은 **두 제품에서 동일하게** 재현됩니다.

**`/db/STCT` — 12개 필드는 저장되고 `iITER`·`TOL` 두 개만 사라집니다.** 응답은 두
필드를 정확히 반환하고, 직후 GET에서만 사라집니다. `FINAL_STAGE`, `CPFC`, `bCONV`,
`bTRUSS`, `bBEAM`, `bCAMBER`, `bCHANGE_CABLE`, `iNLA_TYPE`, `bINC_TDE`, `bCNS`, `TYPE`,
`iITER_CR`, `TOL_CR`는 모두 정상 저장됩니다. `iITER` 값을 바꿔 2회 반복했고 결과는
같았습니다. Civil은 기본 레코드가 이미 있어 PUT으로, Gen은 POST 직후 첫 GET에서
동일하게 나타납니다 — 제품에 무관한 동작입니다.

추정되는 원인을 적어 둡니다: 보낸 페이로드가 매뉴얼 예제 그대로 `iINC_NLA=0`(Linear)과
`iNLA_TYPE=1`(Accumulative)을 함께 담고 있습니다. Accumulative에서 Linear 전용 두 필드를
무시하는 것이 의도된 동작이라면, **무시했다는 사실을 응답이나 경고로 알려 주시면**
호출 측이 대응할 수 있습니다.

**`/db/SBDO`·`/db/SINF`·`/db/MVLDpl` — POST가 201을 반환하고 레코드가 없습니다.**
세 곳 모두 **빈 테이블에 id `1`을 요청**한 경우이므로, 서버가 다른 id로 재부여했을
가능성은 배제됩니다 — 요청한 id가 곳 다음 빈 번호입니다. 전체 테이블을 조회해도
비어 있습니다. `/db/MADO`(id 92)와 `/db/DOEL`(id 4)도 같은 증상을 보이지만, 이 둘은
기존 레코드가 있는 테이블이라 재부여 가능성을 배제하지 못해 위 세 곳과 분리해
적어 둡니다.

세 경우 모두 호출 측이 실패를 알 방법은 다시 조회해 보는 것뿐입니다.

## A-4. 오류 본문이 HTTP 200 / 201로 반환됩니다

```text
POST /db/TDMT   -> 201  {"error": {"message": "Wrong Field"}}
PUT  /db/TMAT   -> 200  {"error": {"message": "Wrong DB Name"}}
POST /doc/ANAL  -> 200  {"message": "MIDAS CIVIL NX Analysis failed."}
```

마지막 사례는 `error` 키 없이 `message`로만 오는데, 성공 시에도 같은 키를
사용하므로(`"... command complete"`) 상태 코드와 응답 키만으로는 성공·실패를 판정할 수
없습니다.

## A-5. `/mapikey/verify`가 종료된 프로그램에 `"connected"`를 반환합니다

```text
GET /mapikey/verify   -> 0.5초, {"status": "connected"}   <- 프로그램은 이미 종료됨
GET /db/NODE          -> 15초 타임아웃
```

영구적으로 잘못된 값은 아닙니다. 크래시 직후 호출 시 두 차례 `"connected"`였고, 약 30초
뒤에는 `"disconnected"`가 반환되었습니다. **연결 기록이 갱신되기 전까지 낡은 값을 주는
구간**이 있고, 그 구간 때문에 자동화 스크립트의 사전 점검으로 사용할 수 없습니다.

## A-6. `"Wrong Field"`가 실제로는 값 오류를 의미합니다

`/db/TDMT`·`/db/TDME`에서 `CODE`/`CODENAME` 값이 인식되지 않을 때 반환됩니다.

```text
값이 인식되지 않음        -> "Wrong Field"
값은 인식되나 필드 부족   -> "[Error] Time Dependent Material(...) input data contain errors."
```

두 메시지가 구분되어 있는 것은 유용합니다. 다만 `"Field"`라는 단어 때문에 필드 **이름**을
의심하게 됩니다. 실제로 이 문제를 추적할 때 문서상 모든 필드를 하나씩 제거하고 단일 키
페이로드까지 시도한 뒤에야 `CODE` 값이 원인임을 발견했습니다.
`"Unknown value for field 'CODE'"` 정도로 필드명을 함께 주시면 진단이 훨씬 빨라집니다.

## A-7. 쓸 수 없는 경로로의 파일 기록이, 실패를 알리지 않거나 세션을 차단합니다

```text
C:\Program Files\MIDAS\MIDAS CIVIL NX\DgnPlugIn\_restore.mcb  -> 액세스 거부 (크래시 복구, 2회)
C:\Users\<user>\Downloads\제목 없음_restore.mcb                -> 정상 저장 (1회)
```

문서 상태에 따라 경로가 달라지며, `Program Files` 하위인 경우 일반 사용자 권한으로
기록할 수 없어 **복구가 조용히 실패합니다.**

**2026-07-29 추가 재현: 크래시 복구뿐 아니라 평범한 읽기 호출에서도 재현됩니다.**
`Program Files\MIDAS\MIDAS CIVIL NX\MIDAS CIVIL NX\Tutorial\5 FCM General.mcb`
(제품 제공 튜토리얼 파일)를 열어둔 상태에서 `GET /db/CAMB`(FCM Camber Control)를
호출하면, API 응답 자체는 `{"message": ""}`로 정상 도착하지만 화면에는
`"...5 FCM General.mcb 액세스가 거부되었습니다."` 모달이 뜹니다. 같은 문서를
쓰기 가능한 폴더(`다운로드`)로 옮긴 뒤 동일한 호출을 반복하면 모달이 뜨지 않고
조용히 넘어갑니다 — 같은 세션, 같은 호출, 문서 경로만 바꾼 A/B로 확인했습니다.
즉 이 문제는 크래시 복구 한정이 아니라, **문서가 쓰기 불가능한 경로에 있을 때
특정 조회성 명령이 내부적으로 보조 파일을 쓰려고 시도하면서 발생하는 더 넓은
패턴**으로 보입니다. `Program Files`처럼 일반 사용자 쓰기 권한이 없는 경로에
문서를 두지 않도록 안내하시거나, 서버 쪽에서 쓰기 실패를 조용히 무시하고 조회
결과만 반환하도록 처리하시는 편이 안전할 것 같습니다.


### 2026-09-21 재측정 — 실패 형태가 제품별로 다릅니다

폐기용 더미 모델을 만들어 `POST /doc/SAVEAS`로 `C:/Program Files/` 아래에 직접
저장을 시도했습니다. 해당 계정은 그 폴더에 쓸 수 없습니다 — 같은 PC에서 제품 GUI의
다른 이름으로 저장을 써도 Windows가
`"이 위치에 저장할 권한이 없습니다"`로 거부합니다. 즉 **두 제품 모두 파일을 쓰지
못하는 것이 정상이고, 문제는 그 사실을 API가 어떻게 알리는가입니다.**

| 제품 | `/doc/SAVEAS` 응답 | 세션 | 파일 |
| --- | --- | --- | --- |
| CIVIL NX | `{"message": "MIDAS CIVIL NX command complete"}` | 정상 | **생성되지 않음** |
| GEN NX | **응답 없음**(60초 타임아웃) | **차단** | 생성되지 않음 |

Gen 화면에 뜬 대화상자는 다음과 같으며, 확인을 누를 때까지 모든 `/db/*` 호출이
타임아웃됐습니다.

> `C:/Program Files/a7-probe-gen-20260921T072357Z.mgbx 액세스가 거부되었습니다.`

**Civil 쪽이 더 문제라고 봅니다.** 성공 메시지가 정상 저장과 글자 단위로 같아서,
호출자가 응답만으로는 구분할 방법이 없습니다. 같은 세션에서 연속으로 측정한
사슬입니다.

```text
SAVEAS C:/temp/a7-chain-civil-....mcbz            -> "MIDAS CIVIL NX command complete"
SAVEAS C:/Program Files/a7-chain-civil-....mcbz   -> "MIDAS CIVIL NX command complete"   (동일)
OPEN   C:/Program Files/a7-chain-civil-....mcbz   -> "MIDAS CIVIL NX path is wrong (the file can't open)"
OPEN   C:/temp/a7-chain-civil-....mcbz            -> "MIDAS CIVIL NX command complete"   (노드 10개 복원)
```

**제품은 알고 있습니다.** 바로 뒤의 `/doc/OPEN`은 그 파일이 없다고 정확히 답합니다.
쓰기가 실패했다는 정보가 `/doc/SAVEAS` 응답에만 담기지 않습니다. `/doc/OPEN`이
내는 것과 같은 수준의 메시지를 `/doc/SAVEAS`도 반환해 주시면 충분합니다.

Gen은 차단되는 대신 사람에게는 사실대로 알립니다. 두 제품이 같은 호출·같은 경로에
대해 이렇게 다르게 동작하는 이유도 함께 확인해 주시면 감사하겠습니다.

**함께 확인된 것 하나를 덧붙입니다.** Gen이 차단된 동안 `/mapikey/verify`는 계속
**1초 이내에 `connected`**를 반환했습니다(수 분 간격 2회). A-5와 같은 현상이며,
이번에는 크래시가 아니라 모달 대기 상태에서 관측됐습니다 — 릴레이가 응답하므로
제품이 멈춘 것을 볼 수 없습니다.

위 2026-07-29의 `GET /db/CAMB` 사례(제품 동봉 튜토리얼 파일을 `Program Files`에서
직접 연 상태)는 이번에 다시 측정하지 않았습니다.

## A-8. `/info/{endpoint}`가 `/DESIGN/*` 계열과 Hyper-S `IEHG` 3종에는 제공되지 않습니다

2026-09-01에 두 SDK에서 각각 전 엔드포인트를 훑었고, 2026-09-03에 응답 전체를 스냅샷으로
보관했습니다(`schema/info-baseline.json`, GET 전용).

| 계열 | `/info` 응답 |
| --- | --- |
| `/db/*` | 402쌍 중 **399쌍**이 스키마 반환 |
| `/DESIGN/*` | **147쌍 전부 404** |
| `/db/IEHG-GL-M1`·`/db/IEHG-PSS-M1`·`/db/IEHG-TRUSS-M1` | 404 (`/db/*`의 나머지 3쌍) |

`GET /DESIGN/RC/KDS-41-20-2022/DCTL`은 정상 응답하는데
`GET /info/DESIGN/RC/KDS-41-20-2022/DCTL`은 404입니다. 대소문자 조합을 바꿔도 같습니다.
엔드포인트 자체는 살아 있으므로 URL 오류가 아니라 **`/info`의 적용 범위가 `/db/*`로
한정된 것**으로 보입니다.

영향은 문서 이상입니다. 설계 코드 계열은 필드 구성을 확인할 수단이 매뉴얼밖에 없어,
B-4(`/db/REBW`)처럼 매뉴얼이 틀린 경우 대조할 대상이 없습니다. `/db/REBW`의 실제 스키마를
찾을 수 있었던 것은 그 엔드포인트가 `/db/*`라서 `/info`가 답했기 때문입니다.
Hyper-S `IEHG` 3종은 공식 섹션이 URL과 메서드만 기재하고 있어, `/info`까지 404이면
**필드를 알 수 있는 경로가 아예 없습니다.**

## A-9. `/info` 스키마가 실제 수용 필드와 양방향으로 어긋납니다

`/info`는 제품 자신이 내보내는 스키마이므로 매뉴얼보다 정확할 것으로 기대했고 실제로
대부분 그렇습니다. 다만 두 방향 모두에서 어긋나는 사례가 확인됐습니다 — **선언했는데
거부하는 필드**와 **선언하지 않았는데 수용하는 필드**입니다.

| 방향 | 대상 | 내용 |
| --- | --- | --- |
| 선언 O / 수용 X | `/db/POSL` (Civil) | `/info`가 `CODE`를 선언하지만, `CODE`를 보내면 **빈 문자열 `""`이라도** `Wrong Field` |
| 선언 X / 거부도 안 함 | `/db/STBK` (양 제품) | `/info`에 `LCNAME`이 없는데, `LCNAME`을 포함해 보내도 오류 없이 처리됩니다 |

`/db/POSL`은 필드별 이진 탐색으로 `CODE`가 단독 원인임을 확인했습니다. 같은 엔드포인트의
Gen NX `/info`는 `CODE`를 포함한 15개 필드를 선언하고 실제로도 수용하므로, 이 엔드포인트의
실제 계약은 **제품별로 다릅니다**. Civil `/info`가 Gen 쪽 필드 목록을 함께 내보내고 있는
것으로 보입니다.

`/db/STBK`은 반대 방향이고, **근거는 `/db/POSL`보다 약합니다.** 양 제품의 `/info`
모두 `DX`/`DY`/`DZ`/`GROUP_NAME`/`NODE1`/`NODE2` 6개만 선언하는데, `LCNAME`을 포함한
요청이 두 제품에서 오류 없이 받아들여집니다. 다만 2026-09-21 재측정 결과, 이어진
`GET`이 돌려주는 레코드에는 `LCNAME`이 **없습니다.** 즉 확인된 것은 "거부하지 않는다"까지이고,
저장되는지·효과가 있는지는 측정하지 못했습니다. 이 필드의 취급을 알려 주시면 감사하겠습니다.

두 사례 때문에 `/info`를 **수용 필드의 상한으로도 하한으로도** 쓸 수 없습니다. 자동화
도구가 `/info`로 요청을 검증하면 `/db/STBK`의 정상 요청을 막고 `/db/POSL`의 실패 요청을
통과시킵니다. 두 엔드포인트의 스키마 출처를 확인해 주시면 감사하겠습니다.

## A-10. 문서화된 형태로 쓰기가 되지 않는 엔드포인트 — 동작하는 최소 페이로드를 요청드립니다

앞의 항목들과 달리 **결함으로 단정하지 않습니다.** 저희가 찾지 못한 것일 수
있습니다. 다만 아래 엔드포인트들은 **시도한 모든 페이로드가 거부**되어 쓰기 경로를
한 번도 통과하지 못했고, 두 제품에서 동일합니다. 각각 동작하는 최소 요청 본문을
하나씩만 알려 주시면 나머지는 저희가 맞추겠습니다.

| 대상 | 응답 | 값 문제가 아니라고 보는 근거 |
| --- | --- | --- |
| `/db/WVLD` | `Wrong Field` | `{"NAME": ...}` **하나만 보내도** 동일. 페이로드 안의 어느 값도 원인이 될 수 없습니다 |
| `/db/EPST`·`/db/EPSE` | `Wrong Field` | `SEL_TYPE`·`EP_TYPE`·`ELEM_TYPE`·`DIR` **네 필드의 문서화된 값을 하나씩 전부** 시도 |
| `/db/TDMF` | `Wrong Field` | 이 요청이 보내는 필드 중 값 집합이 명시된 것이 없습니다 |
| `/db/HPCE` | `Wrong Key` | — |
| `/db/FBLA`·`/db/PHGE`·`/db/MVLDeu`·`/db/NLLP` | `Unknown Error` | 메시지에 단서가 없습니다 |

`Unknown Error` 네 건은 A-6과 같은 요청이기도 합니다 — **어느 필드가 문제인지를
메시지에 담아 주시면** 이 리포트의 상당 부분은 애초에 생기지 않았을 것입니다.

`/db/RPSC`는 조금 다릅니다. `GET /info/db/RPSC`가 `MBARS[].MBAR_ITEMS[].PART`를
선언하는데, 이 필드는 **기본값도 필수 여부도 예제도 없습니다.** 값을 지어내서
보내는 것은 이 리포트의 원칙에 맞지 않아 거기서 멈췄습니다. 이 필드의 의미와
허용 값을 알려 주시면 감사하겠습니다.

---

# B. 문서 관련

제품 동작은 정상이며, 공식 온라인 매뉴얼(JSON Manual 섹션) 기재 내용과 관련된 항목입니다.
B-1~3은 **2026-07-27자**, B-4는 **2026-07-29자 및 2026-08-27자**, B-5는 **2026-08-27자**
공식 아티클 원문을 직접 확인한 결과만 남긴 것입니다.

| # | 대상 | 아티클 | 내용 |
| --- | --- | --- | --- |
| B-1 | `/db/PRES` | Assign Pressure Loads | `DIRECTION`이 `Optional / 기본값 "NORMAL"`인데, 각주 ¹⁾ 표에서는 해당 조합에 `NORMAL`이 불가로 표기 |
| B-2 | `/db/MVHC` | Vehicle Classes | 예시의 `VEHICLE_LD_NAMES: ["DB-18"]`이 그대로는 동작하지 않음 |
| B-3 | `/db/STLD` | Static Load Cases | `"Assign"` 키의 의미가 명시되어 있지 않음 (이 엔드포인트는 키를 무시하고 재부여) |
| B-4 | `/db/REBW` | Modify Wall Rebar Data | Specifications 표의 필드명이 서버 구현과 전혀 다름 (`VERTICAL_REBAR` 등 vs 실제 `VER_BAR` 등) |
| B-5 | `/db/REBC` | Modify Column Rebar Data | `Active Methods`(POST만)와 주철근 필드 구조(`MAIN_BAR` 단일 객체)가 서버 구현과 다름 |

## B-1. `/db/PRES` — `DIRECTION`의 기본값과 각주가 서로 맞지 않습니다

각주 ¹⁾의 표는 실제 동작을 **정확히** 기술하고 있습니다.

| Element Types | Normal | Local x/y/z | Global X/Y/Z | Vectors |
| --- | --- | --- | --- | --- |
| `"PLATE"` `"FACE"` | **-** | O | O | O |
| `"PLATE"` `"EDGE"` | O | O | O | O |
| `"SOLID"` `"PRES"` | O | O | O | O |

다만 Specifications 표의 `DIRECTION` 행은 `Default: "NORMAL"`, `Required: Optional`로
되어 있습니다. `PLATE` + `FACE` 조합에서는 두 기술이 양립할 수 없고, 실제로 **필드를
생략하면 요청이 실패합니다.**

```python
# PLATE + FACE, DIRECTION 생략 -> 실패
# PLATE + FACE, DIRECTION: "LZ" -> 정상
```

해당 조합에서는 `DIRECTION`을 Required로 표기하거나, 기본값에 예외를 병기해 주시면
좋겠습니다.

## B-2. `/db/MVHC` — 예시를 그대로 실행하면 `Unknown Error`가 발생합니다

공식 예시는 아래와 같습니다.

```json
{ "Assign": { "1": { "VEHICLE_CLS_NAME": "VCN1",
                     "VEHICLE_LD_NAMES": ["DB-18"] } } }
```

`VEHICLE_LD_NAMES`는 "Selected Vehicle List"로, `/db/MVHL`에 정의된 차량의
`VEHICLE_LOAD_NAME`을 넣어야 합니다. `"DB-18"`은 표준 차량의 **종류명**이어서, 같은 이름의
차량을 먼저 정의해 두지 않으면 `Unknown Error`로 거부됩니다.

선행 조건(`/db/MVHL` 정의가 먼저 필요하다는 점)을 한 줄 덧붙여 주시거나, 예시를
사용자가 지정한 이름으로 바꿔 주시면 좋겠습니다. 참고로 실패 시 메시지가
`Unknown Error`뿐이라 원인 파악이 어렵습니다(A-6과 같은 사안입니다).

## B-3. `/db/STLD` — `"Assign"` 키가 ID로 쓰이지 않는다는 설명이 없습니다

대부분의 `/db/*` 엔드포인트는 `"Assign"`의 키가 곧 레코드 ID입니다(`/db/NODE`에 키
`9001`로 쓰면 절점 9001이 생성됩니다). 그런데 `/db/STLD`와 `/db/TDME`는 키를 무시하고
**다음 빈 번호로 재부여**합니다.

```python
call("POST", "/db/STLD", {"Assign": {"7": {"NAME": "LC7", "TYPE": "D"}}})
call("GET",  "/db/STLD")
# -> 생성된 ID는 3 (7이 아님)
```

Specifications 표는 `"NO"`를 `Read Only`로만 표기하고 있고, `"Assign"` 키가 어떻게
처리되는지는 나와 있지 않습니다. 키를 존중하는 테이블과 재부여하는 테이블이 섞여 있으므로,
재부여하는 엔드포인트에는 그 사실을 명시해 주시면 좋겠습니다.

## B-4. `/db/REBW` — Specifications 표의 필드명이 서버 구현과 완전히 다릅니다

실제 프로덕션 Gen NX 모델(한국 KDS 기준, 벽체 철근 102건 실데이터)로 확인했습니다.
매뉴얼 Specifications 표는 다음을 기재하고 있습니다:

```
CREATE_SUB_WALL_ID, SUB_WALL_ID, STORY: {FROM, TO},
VERTICAL_REBAR: {NAME, DIST}, HORIZONTAL_REBAR: {NAME, DIST},
USE_END_REBAR, END_REBAR: {NAME, NUM, DIST},
BE_HORIZONTAL_REBAR: {NAME, DIST}, BOUNDARY_ELEMENT_LENGTH,
CONCRETE_FACE_TO_CENTER_OF_REBAR: {DW, DE},
USE_MODEL_THICKNESS, THICKNESS
```

그런데 실제 `GET /db/REBW` 응답과 `GET /info/db/REBW` 스키마는 다음입니다:

```
{"ID": 0, "bUSE_MODEL_THICK": true, "THICK": 0, "DW": 0.05, "DE": 0.05,
 "VER_BAR": {"NAME": "D16", "DIST": 0.2},
 "HOR_BAR": {"NAME": "D13", "DIST": 0.25},
 "END_BAR": {"NAME": "", "DIST": 0}, "NUM_END_BAR": 0,
 "BE_HOR_BAR": {"NAME": "D10", "DIST": 0.2}, "BE_LENGTH": 0}
```

`STORY`는 `{FROM,TO}` 범위가 아니라 `vSTORY_NAME`(층 이름 문자열 배열)입니다. 필드명이
하나도 일치하지 않고, `DW`/`DE`는 중첩 없이 최상위로 나옵니다. **PUT으로 실제 확인**했습니다
— 기존 벽체 하나의 값을 백업한 뒤 `/info` 스키마의 필드명으로 값을 바꿔 보냈더니 정상
반영됐고, 재조회로 확인 후 원래 값으로 복원했습니다.

같은 세션에서 같은 모델의 형제 엔드포인트로 교차 확인했습니다: `/db/REBB`(같은 챕터)와
`/DESIGN/RC/KDS-41-20-2022/REBW`(KDS 전용 벽체 철근, 같은 물리 벽체 102건)는 **둘 다
자신의 문서와 정확히 일치**했습니다. 즉 철근 관련 엔드포인트 전체의 문제가 아니라,
**`/db/REBW`의 Specifications 표 하나만** 실제 서버 구현과 다른 것으로 보입니다.

공식 온라인 매뉴얼로 직접 재확인한 결과입니다 — 참조 사본의 전사 오류가 아닙니다.
[공식 아티클](https://support.midasuser.com/hc/en-us/articles/59359110968345-Modify-Wall-Rebar-Data)도
`VERTICAL_REBAR`/`HORIZONTAL_REBAR`/`CONCRETE_FACE_TO_CENTER_OF_REBAR`/`STORY: {FROM,TO}` 등
긴 이름 그대로 기재되어 있습니다. 즉 **공식 문서 자체가 실제 서버와 다릅니다.**

**2026-08-27 재확인:** 같은 문서를 담고 있는 별도 article id
([49514033006745](https://support.midasuser.com/hc/en-us/articles/49514033006745-Modify-Wall-Rebar-Data))도
직접 조회했으며, 동일하게 `VERTICAL_REBAR`/`CREATE_SUB_WALL_ID` 등 실제 서버와 다른 필드명을
기재하고 있습니다. `GET /info/db/REBW` 스키마도 재조회해 위 필드 구성(`VER_BAR`/`HOR_BAR`/
`vSTORY_NAME` 등)이 그대로임을 확인했습니다.

## B-5. `/db/REBC` — `Active Methods`와 주철근 필드 구조가 서버 구현과 다릅니다

[공식 아티클](https://support.midasuser.com/hc/en-us/articles/49513980544793-Modify-Column-Rebar-Data)은
다음과 같이 기재하고 있습니다.

- `Active Methods: POST` (POST만 지원)
- 주철근 필드가 단일 객체 `MAIN_BAR: {NAME, NUM, ROW, USE_CORNER, NAME_CORNER}`

실제 Gen NX 서버는 `GET`/`PUT`/`DELETE`가 모두 정상 동작하며(POST 전용이 아님), 주철근
필드는 배열 `vMAIN_BAR: [{NAME, NUM, ROW, D0, bUSE_CORNER, NAME_CORNER}, ...]`입니다.

```python
# 문서 기재 형태로 요청
{"Assign": {"1": {"ITEMS": [{
    "MAIN_BAR": {"NAME": "D19", "NUM": 8, "ROW": 3, "USE_CORNER": False, "NAME_CORNER": "D19"},
    "SHEAR_BAR_END": {"NAME": "D10", "LEG_Y": 2, "LEG_Z": 2, "DIST": 100},
    "SHEAR_BAR_CEN": {"NAME": "D10", "LEG_Y": 2, "LEG_Z": 2, "DIST": 200},
    "DO": 0.04,
}]}}}
# -> "Wrong Field" (필드 자체가 인식되지 않음)

# 실제 서버 스키마(vMAIN_BAR 배열) 형태로 동일 조건 요청
{"Assign": {"1": {"ITEMS": [{
    "vMAIN_BAR": [{"NAME": "D19", "NUM": 8, "ROW": 3, "D0": 0.04,
                   "bUSE_CORNER": False, "NAME_CORNER": "D19"}],
    "SHEAR_BAR_END": {"NAME": "D10", "LEG_Y": 2, "LEG_Z": 2, "DIST": 100},
    "SHEAR_BAR_CEN": {"NAME": "D10", "LEG_Y": 2, "LEG_Z": 2, "DIST": 200},
    "HOOP_TYPE": 1, "bSAME_SPACE_END_CEN": True, "NUM_BAR_BC_JOINT": 0,
}]}}}
# -> 정상 처리되어 도메인 에러(대상 섹션 번호 관련) 응답 -- 요청 형태 자체는 인식됨
```

`GET /info/db/REBC` 스키마도 배열 구조(`vMAIN_BAR`)와 정확히 일치하며, 문서에는 없는
`HOOK_TYPE` 필드도 포함되어 있습니다. `GET /db/REBC` 역시 정상 응답해 `Active Methods:
POST`만이라는 기재와 배치됩니다.

테스트 환경: MIDAS Gen NX 2026 (v2.1). B-4(`/db/REBW`)와 같은 챕터의 인접 엔드포인트이며,
공식 문서 자체가 실제 서버와 다르다는 같은 패턴입니다.

---

# 부록

- 전 항목을 v2.2 단일 세션에서 심각도 역순으로 일괄 재검증했습니다(문서 → 응답 규약 →
  무언 실패 → 테이블 삭제). A-2는 v2.1에서도 확인했습니다.
- 모든 항목은 응답 확인에 그치지 않고 **다시 조회해 저장 결과를 비교**했습니다. A-3의
  10건은 이 비교 없이는 발견되지 않습니다.
- 검증 중 제기했다가 **재현되지 않아 제외한 항목 2건**입니다. 확인차 적어 둡니다.
  - `/db/MVHL`에 `VEH_DEFAULT: {}` 전송 — v2.1에서는 저장되지 않고 `{"message": ""}`가
    반환되었으나, v2.2에서는 정상 저장되며 기본값이 채워져 반환됩니다. 조치된 것으로
    보입니다.
  - `/db/PSLT`의 `ELEM_TYPE` 표기 — 본문(`"Plate/Plane Stress (Face)"`)과
    예시(`"Plate/PlaneStress(Face)"`) 표기가 다르지만 **두 표기 모두 허용**되어 제품
    문제가 아닙니다. 매뉴얼 내 표기만 통일해 주시면 됩니다.

- 문서 관련 항목은 발송 전 **2026-07-27자 공식 아티클 원문과 다시 대조**했고, 그 결과
  당초 작성했던 7건 중 **4건을 저희 쪽 오류로 판단해 철회**했습니다. 공식 문서는 정확했고,
  저희가 참조하던 사내 정리본의 전사 오류였습니다. 기록 차원에서 남깁니다.

  | 철회 항목 | 저희가 주장하려던 내용 | 공식 아티클 실제 기재 |
  | --- | --- | --- |
  | `/db/TDMT` `CODE` | "CEB-FIP 표기를 전부 거부한다" | `CEB_FIP_2010`·`CEB`·`KDS_2016`·`EUROPEAN` 등 **28개 값이 정확히 명시**되어 있음. 저희가 시험한 값은 같은 예시의 `NAME`(표시용 이름)이었습니다 |
  | `/db/TDME` `CODENAME` | "`KDS2016`이 거부된다" | 공식 표기는 `KDS-2016`. `KDS2016`은 공식 문서에 없는 표기였습니다 |
  | `/db/SECF` 키 | "예시 키가 element로 읽힌다" | 공식 아티클은 키의 의미를 언급하지 않으며, element라고 쓴 적이 없습니다 |
  | `/db/PRES` `FORCES` | "예시가 4개인데 5개로 반환된다" | 공식 표기가 `Array [Number, 5]`이고 예시도 모두 5개입니다. `PSLT_KEY`도 공식 스키마에 있습니다 |

  참고로 `/db/TDMT`는 `UNDERSCORED_UPPERCASE`(`CEB_FIP_2010`), `/db/TDME`는 표시용
  문자열(`CEB-FIP(2010)`)을 쓰는 것으로 **두 엔드포인트의 표기 규칙이 다릅니다.** 양쪽 다
  문서에는 정확히 적혀 있으나, 같은 코드를 다르게 표기해야 하는 점은 혼동하기 쉬웠습니다.

## v1.4 변경 내역 (2026-09-21)

| 구분 | 내용 |
| --- | --- |
| A-1 | **삭제** — `POST /db/NMAS`에서 `rmX`/`rmY`/`rmZ`를 생략했을 때의 종료. 조치된 것을 확인했습니다(아래) |
| A-3 | 7건 추가 — `/db/MATD`(Civil)·`/db/SPLC`(Gen)·`/db/SSEIS`(Gen), 그리고 두 제품 공통인 `/db/STCT`·`/db/SBDO`·`/db/SINF`·`/db/MVLDpl`. 기존 3건은 변동 없음 |
| A-8 | 신규 — `/info`가 `/DESIGN/*` 147쌍과 Hyper-S `IEHG` 3종에 제공되지 않음 |
| A-9 | 신규 — `/info`가 실제 수용 필드와 양방향으로 어긋남 (`/db/POSL`, `/db/STBK`) |
| A-10 | 신규 — 쓰기가 한 번도 통과하지 못한 9개 엔드포인트와 `/db/RPSC`. 결함 주장이 아니라 동작 예시 요청 |
| B | 변동 없음 |

v1.3 이후의 **문서 관련 지적은 이 리포트에 넣지 않았습니다.** 2026-09-18에 매뉴얼 담당
쪽 요청으로 진행한 표기·타입 확인(`/ope/MEMB`의 `SELETION_TYPE`, `/db/SSEIS`의 KDS 코드
표기, `/db/TDNA`의 `RADIUS` 타입 3건)은 매뉴얼 채널로 별도 회신했습니다. 그 확인 과정에서
드러난 **제품 동작** 3건만 위 A-3에 올렸습니다.

**A-1은 조치된 것을 확인해 이번 판에서 제외했습니다.** `rmX`/`rmY`/`rmZ`를
생략한 원본 재현 호출(SDK를 거치지 않는 단일 스크립트)이 **두 제품 모두 Build
09/15/2026에서 201을 반환하고 세션이 유지**되며, 이어진 GET에서 서버가 세 필드를
문서화된 기본값 `0`으로 직접 채워 돌려줍니다. "죽지 않는다"가 아니라 **기본값이
적용된다**는 점까지 확인했습니다. 3회 연속 정상이며, 조치해 주셔서 감사합니다.

A-8·A-9는 결함이라기보다 **확인 요청**에 가깝습니다. 다만 `/info`를 신뢰해 요청을
사전 검증하는 도구가 실제로 잘못 판정하므로, 의도된 동작인지 알려 주시면 그에 맞춰
도구 쪽을 조정하겠습니다.

추가 정보나 재현 로그가 필요하시면 말씀해 주세요.
