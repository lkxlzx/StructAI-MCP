# midas-nx 시작 가이드 (프로그래밍이 처음이신 분도 괜찮습니다)

이 가이드는 MIDAS Gen NX/Civil NX를 실무에서 쓰시지만 Python이나 프로그래밍은
처음이신 구조 엔지니어를 위한 것입니다. Python 설치부터 첫 스크립트 실행까지,
한 번에 끝까지 따라 할 수 있도록 순서대로 안내합니다.

> 개발 경험이 있으시다면 [README.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/README.md)의 Quick Start가 더 빠릅니다.
> 이 가이드는 그 전 단계 — "Python이 뭔지도 잘 모르겠다"는 분들을 위한 것입니다.

> `midas-nx`는 마이다스아이티 재직자가 실제 제품·API 검증 경험을 바탕으로
> 개발·관리하는 **직원 주도형 오픈소스 프로젝트**입니다. 마이다스아이티가 공식적으로
> 출시하거나 기술지원하는 제품은 아니므로, 이 가이드나 SDK에 대한 문의를 제품
> 기술지원으로 보내시면 답을 받으실 수 없습니다. SDK 문제는
> [GitHub Issues](https://github.com/Dennis5882/MIDAS-API-NX-SDK/issues)로 알려주세요.

## 시작하기 전에 필요한 것

- Windows PC (이 가이드는 Windows 기준으로 설명합니다)
- MIDAS Gen NX 또는 Civil NX 설치 및 정상 라이선스
- 인터넷 연결 (MIDAS 클라우드 릴레이 서버를 통해 통신합니다)

## 1단계: Python 설치하기

`midas-nx`는 **Python 3.11 이상**이 필요합니다 — 3.11, 3.12, 3.13, 3.14를
CI에서 모두 검증합니다.

1. https://www.python.org/downloads/ 에 접속해 최신 버전 다운로드 버튼을
   누르면 됩니다. 이미 3.11 이상이 깔려 있다면 새로 설치할 필요가 없습니다.
2. 설치 파일을 실행합니다. **이때 설치 화면 맨 아래의 "Add python.exe to PATH"
   체크박스를 반드시 체크**한 뒤 "Install Now"를 누르세요. 이 체크를 빠뜨리면
   나중에 명령 프롬프트가 `python`을 인식하지 못합니다.
3. 설치가 끝나면 확인해봅니다. 시작 메뉴에서 "cmd"를 검색해 명령 프롬프트를 열고
   다음을 입력하세요.

   ```
   python --version
   ```

   `Python 3.11.x` 이상이 나와야 합니다. 더 예전 버전(예: `Python 3.10.x`)이
   깔려 있었다면 위 방법으로 새로 설치하세요 — 다음 단계에서 `pip install`이
   3.11 미만에는 `midas-nx` 설치를 거부합니다. `'python'은 내부 또는 외부
   명령... 이 아닙니다` 같은 오류가 뜨면 2번의 PATH 체크를 빠뜨린 것이니
   Python을 다시 설치해보세요.

## 2단계: midas-nx 설치하기

같은 명령 프롬프트에서 다음을 입력합니다.

```
python -m pip install midas-nx
```

(그냥 `pip` 대신 `python -m pip`를 쓰면, PC에 Python이 여러 버전 깔려 있을
때 엉뚱한 버전에 설치되는 걸 막아줍니다 — `pip install 패키지명` 형태만
보셨더라도 이 방식을 쓰는 게 더 안전합니다.)

`Successfully installed midas-nx-...`라는 메시지가 뜨면 설치 완료입니다.

## 3단계: MAPI 키 확인하기

`MAPI-Key`는 이 SDK가 MIDAS Gen NX/Civil NX와 통신할 때 쓰는 인증 키로,
Python이 아니라 **MIDAS Gen NX(또는 Civil NX) 프로그램 안에서** 직접
확인합니다.

1. MIDAS Gen NX(또는 Civil NX)를 실행합니다.
2. 상단 메뉴 **Apps**에서 **API Settings**를 클릭합니다.
3. 화면에 **Base URL**과 **MAPI-Key**가 표시됩니다. 각각 옆의 **Copy** 버튼을
   누르면 자동으로 복사됩니다.
4. **Connected**를 클릭합니다. 성공하면 Status가 **Connected**로 바뀝니다 —
   이렇게 되어야 Open API가 실제로 켜진 상태입니다.

> 키를 새로 받고 싶다면(예: 유출이 의심될 때) 옆의 **Refresh** 버튼을
> 누르면 됩니다. 기존 키는 그 즉시 무효화됩니다.

> ⚠️ **키가 살아있는 동안에는 비밀번호처럼 다루세요.** 아래 스크립트들은
> 편의를 위해 키를 코드에 직접 붙여넣는데, 본인 PC의 일회성 파일이라면
> 괜찮지만 이 파일을 Git에 커밋하거나, 공개 채팅·이슈에 붙여넣거나, 키가
> 보이는 스크린샷을 공유하지는 마세요. 유출된 것 같다면 위 **Refresh**로
> 새 키를 받으면 됩니다 — 기존 키도 프로그램을 종료하면 어차피 만료됩니다.

> 🌏 **어느 지역 서버를 쓰는지 추측할 필요가 없습니다.** 위 화면에 표시된
> **Base URL**을 그대로 쓰면 됩니다 — 중국 서버를 포함해 어떤 리전이든
> 마찬가지입니다. 기본 글로벌 서버(`moa-engineers.midasit.com`)와 다르면
> 아래 `MidasClient(...)` 호출에 `base_url="복사한 값"`을 추가하세요.

> 아래 코드에서 `client = MidasClient(...)`나 `for` 같은 게 낯설게
> 느껴지신다면, 먼저 [Python 기초](python-basics.md)에서 이 가이드에 나오는
> 문법만 짧게 짚어보고 오셔도 좋습니다.

## 4단계: 첫 스크립트 작성하고 실행하기 (읽기 전용)

**위험 등급: 1 — 읽기 전용** ([위험 등급 안내](../safety.md#risk-levels) 참고).

메모장(또는 VS Code 등 아무 텍스트 편집기)을 열어 아래 내용을 그대로
붙여넣습니다. `"여기에_3단계에서_복사한_키_붙여넣기"` 부분만 실제 키로
바꿔주세요.

```python
from midas_nx import MidasClient, Product
from midas_nx.db.node_element import Node

# Civil NX를 쓰신다면 product=Product.CIVIL로 바꾸세요.
client = MidasClient(mapi_key="여기에_3단계에서_복사한_키_붙여넣기", product=Product.GEN)

print(client.verify_connection())

nodes = Node.items(client=client)
print(f"연결 성공. 현재 모델에서 절점 {len(nodes)}개를 찾았습니다.")
```

파일 이름은 `first_script.py`로 저장합니다 (바탕화면이나 원하는 폴더 어디든
괜찮습니다).

명령 프롬프트에서 저장한 폴더로 이동한 뒤 실행합니다. 예를 들어 바탕화면에
저장했다면:

```
cd Desktop
python first_script.py
```

다음과 비슷한 결과가 출력됩니다.

```
{'status': 'connected', 'keyVerified': True}
연결 성공. 현재 모델에서 절점 3개를 찾았습니다.
```

(절점 개수는 현재 열려 있는 모델에 따라 달라집니다 — 빈 프로젝트라면 `0`이
나오는 것도 정상입니다.)

**이 스크립트는 데이터를 읽기만 합니다.** 어떤 프로젝트에 대해 실행하든
모델을 만들거나 바꾸거나 지우지 않으므로, 실무 모델에 대해서도 안심하고
실행해보셔도 됩니다.

## 잘 안 될 때

- **`MidasConnectionError`가 뜬다면**: Gen NX/Civil NX가 실행 중인지, Open API가
  연결되어 있는지 확인하세요. 이 SDK의 에러 메시지는 끝에 `(Hint: ...)` 형태로
  무엇을 확인해야 하는지 알려줍니다.
- **`MidasAuthError`가 뜬다면**: 3단계에서 복사한 키를 스크립트에 정확히
  붙여넣었는지 확인하세요. 키는 프로그램을 껐다 켜면 바뀔 수 있으니, 안 되면
  다시 발급받아 붙여넣어 보세요.
- **회사 방화벽 안에 있다면**:
  ["Connectivity troubleshooting"](../safety.md#connectivity-troubleshooting)에
  IT팀에 전달할 방화벽 허용 정보(포트/주소)가 정리되어 있습니다.

## 5단계: 빈 모델에 데이터 추가하기 (선택 — 모델이 변경됩니다)

**위험 등급: 2 — 제한적 추가** ([위험 등급 안내](../safety.md#risk-levels) 참고).

실행하기 전에, Gen NX/Civil NX에서 **직접 GUI로 새 빈 프로젝트**를
만들어두세요 (File > New Project 등). 이 스크립트는 현재 열려 있는
프로젝트에 데이터를 추가할 뿐, 프로젝트를 새로 만들지는 않습니다. 아래
6단계와 달리 `doc.new_project()`를 호출하지 않으므로 버릴 작업 자체가
없습니다.

```python
from midas_nx import MidasClient, Product
from midas_nx.db.node_element import Node

# Civil NX를 쓰신다면 product=Product.CIVIL로 바꾸세요.
client = MidasClient(mapi_key="여기에_3단계에서_복사한_키_붙여넣기", product=Product.GEN)

Node.create({1: {"X": 0, "Y": 0, "Z": 0}, 2: {"X": 0, "Y": 0, "Z": 3.2}}, client=client)

nodes = Node.items(client=client)
print(f"절점 2개를 추가했습니다. 현재 모델에 절점 {len(nodes)}개가 있습니다.")
```

4단계와 같은 방법으로 실행하세요. `절점 2개를 추가했습니다. 현재 모델에
절점 2개가 있습니다.`가 출력되고(열어둔 빈 프로젝트에 이미 뭔가 있었다면
더 많을 수 있습니다), Gen NX 화면에는 새 점 2개가 보일 겁니다.

## 6단계: 모델을 처음부터 만들어보기 (선택 — 모델이 변경됩니다)

**위험 등급: 4 — 고위험** ([위험 등급 안내](../safety.md#risk-levels) 참고).
`doc.new_project()`가 저장하지 않은 작업을 버리기 때문에, 이 단계는 선택
사항으로 4·5단계와 분리했습니다.

4단계로 연결이 잘 되는지 확인했고, 5단계로 직접 준비한 모델에 안전하게
데이터를 추가해봤습니다. `midas-nx`가 프로젝트 생성부터 모델 전체를
처음부터 만드는 모습까지 보고 싶으시다면, MIDAS-API 매뉴얼이 사용하는
예제를 아래에 준비했습니다 — 실행 전에 경고를 먼저 읽어주세요.

> ⚠️ **이 스크립트는 `doc.new_project()`를 호출하는데, 이는 현재 Gen
> NX/Civil NX에서 열려 있는 문서의 저장하지 않은 작업을 모두 버립니다** —
> 이 스크립트와 관련 없는 작업이라도 마찬가지입니다. 빈 프로젝트에서만
> 실행하거나, 저장 안 한 변경사항을 잃어도 괜찮은 프로젝트에서만 실행하세요.
> 실무 모델이 열려 있다면 먼저 저장하거나(또는 닫고 새 빈 프로젝트를 만든 뒤)
> 실행하세요.

```python
from midas_nx import MidasClient, Product, doc
from midas_nx.db.node_element import Element, Node
from midas_nx.db.project import Unit
from midas_nx.db.properties.material import Material
from midas_nx.db.properties.section import Section

# Civil NX를 쓰신다면 product=Product.CIVIL로 바꾸세요.
client = MidasClient(mapi_key="여기에_3단계에서_복사한_키_붙여넣기", product=Product.GEN)

doc.new_project(client=client)
Unit.update({1: {"DIST": "M", "FORCE": "KN"}}, client=client)

Material.create(
    {1: {"TYPE": "CONC", "NAME": "C24",
         "PARAM": [{"P_TYPE": 1, "STANDARD": "KS01(RC)", "DB": "C24"}]}},
    client=client,
)
Section.create(
    {1: {"SECTTYPE": "DBUSER", "SECT_NAME": "Column",
         "SECT_BEFORE": {"USE_SHEAR_DEFORM": True, "SHAPE": "SB", "DATATYPE": 2,
                          "SECT_I": {"vSIZE": [0.6, 0.6]}}}},
    client=client,
)
Node.create({1: {"X": 0, "Y": 0, "Z": 0}, 2: {"X": 0, "Y": 0, "Z": 3.2}}, client=client)
Element.create({1: {"TYPE": "BEAM", "MATL": 1, "SECT": 1, "NODE": [1, 2]}}, client=client)
doc.save(client=client)

print("성공! Gen NX 화면에서 기둥이 생성된 걸 확인해보세요.")
```

4단계와 같은 방법으로 실행하세요 (`.py` 파일로 저장한 뒤 `python`으로 실행).
`성공! Gen NX 화면에서...`이 출력되고, Gen NX 창으로 전환해보면 0.6m × 0.6m
콘크리트 기둥(높이 3.2m) 하나가 새로 생성되어 있을 겁니다.

> 위 예제의 재료(`C24`/`KS01(RC)`) 조합은 2026-07-22에 실제 Gen NX·Civil NX
> 세션에서 라이브로 검증됐습니다 (자세한 내용은
> [docs/live_verification_notes.md](../live_verification_notes.md) 참고) —
> 임의의 예시가 아니라 확인된 값을 사용했습니다.

## 다음 단계

- **AI 코딩 도구와 함께 확장하기**: 위 스크립트의 패턴만 익히면, 이후로는 직접
  모든 코드를 외워서 쓸 필요가 없습니다. Claude Code·ChatGPT·GitHub Copilot 같은
  AI 도구에 이 스크립트를 보여주고 "기둥 대신 20m 보를 만들어줘", "하중조합을
  추가해줘"처럼 자연어로 요청하면 됩니다. AI가 실제 `midas-nx` 코드로 바꿔줄
  겁니다 — 이 SDK는 애초에 그렇게 함께 쓰기 편하도록 설계되었습니다(타입 힌트,
  명확한 에러 메시지 등). AI가 만들어준 코드를 실행하기 전에는
  [AI 코딩 안전 시작 가이드](ai-coding/safe-start.md)에서 AI에게 줄 context
  pack과 실행 전 검토 체크리스트를 확인하세요.
- 더 실무에 가까운 예제: GitHub의 [`examples/python/`](https://github.com/Dennis5882/MIDAS-API-NX-SDK/tree/main/examples/python/)
  폴더 (보 하중조합, 풍하중, 시공단계 등) — AI에게 "이 예제처럼 만들어줘"라고
  보여줘도 좋습니다.
- 구현된 전체 기능 목록: [ROADMAP.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/ROADMAP.md)
- 더 자세한 사용법·설계 원칙: [README.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/README.md)

이 가이드를 따라 하다 막히는 부분이 있었다면 GitHub Issues에 알려주세요 —
다음 사용자를 위해 가이드를 개선하는 데 큰 도움이 됩니다.
