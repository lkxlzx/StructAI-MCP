# Python 기초: SDK 예제를 이해하는 데 필요한 최소한

이 페이지는 Python을 아예 처음 접하는 분을 위한 것입니다. [시작
가이드](quickstart.md)의 코드를 보고 "이게 뭘 하는 건지 하나도 모르겠다"
싶으시면 여기부터 읽어보세요. Python 전체를 가르치는 강좌가 아니라,
`midas-nx` 예제와 [Recipe](../recipes/index.md)에 실제로 나오는 문법만
딱 그만큼 설명합니다.

> 여기서 다루지 않는 것: 클래스 만들기, 데코레이터, 비동기(async) 코드 등.
> 이런 게 필요해지는 시점이면 이미 이 페이지가 목표로 하는 "완전 초보"
> 단계는 지난 것이니, 그때는 일반 Python 강좌나 책을 보시는 게 낫습니다.

## 변수

값에 이름을 붙이는 것입니다. `=`는 "같다"가 아니라 "오른쪽 값을 왼쪽
이름에 저장한다"는 뜻입니다.

```python
client = MidasClient(mapi_key="abc123", product=Product.GEN)
```

`client`라는 이름에 `MidasClient(...)`가 만들어낸 결과를 저장했습니다.
이후 코드에서 `client`라고 쓰면 이 결과를 다시 쓸 수 있습니다.

## 문자열과 숫자

따옴표(`"..."` 또는 `'...'`)로 감싼 건 문자열(글자), 감싸지 않은 숫자는
그대로 숫자입니다.

```python
name = "midas-nx"      # 문자열
height = 3.2            # 숫자 (소수)
count = 3                # 숫자 (정수)
```

`quickstart.md`의 `Z: 3.2`, `mapi_key="여기에_붙여넣기"`가 각각 숫자와
문자열의 예입니다.

## 리스트

순서가 있는 값의 묶음입니다. 대괄호 `[...]`로 씁니다.

```python
node_ids = [1, 2, 3]
```

## 딕셔너리

"키: 값" 쌍의 묶음입니다. 중괄호 `{...}`로 씁니다. `midas-nx`의 모든
데이터(노드, 요소, 응답 결과)가 이 형태로 오갑니다.

```python
node = {"X": 0, "Y": 0, "Z": 3.2}
print(node["Z"])   # 3.2 출력 — 키로 값을 꺼냅니다
```

quickstart 5단계의 `Node.create({1: {"X": 0, "Y": 0, "Z": 0}, 2: {...}}, ...)`는
"키가 1인 노드는 이 딕셔너리, 키가 2인 노드는 저 딕셔너리"라는 뜻으로,
딕셔너리 안에 딕셔너리가 또 들어있는 형태입니다.

## 함수 호출과 인자

함수 이름 뒤에 괄호를 붙이고 필요한 값(인자)을 넣으면 그 함수가
실행됩니다. `이름=값` 형태로 넣는 건 "키워드 인자"라고 하며, 어떤 값이
무엇을 뜻하는지 이름으로 명확히 알 수 있습니다.

```python
client = MidasClient(mapi_key="abc123", product=Product.GEN)
#                     ^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^^^^
#                     mapi_key라는 인자   product라는 인자
```

`Node.items(client=client)`도 마찬가지입니다 — `client`라는 인자에
앞에서 만들어둔 `client` 변수를 넘겨준 것입니다. 같은 이름이라 헷갈릴 수
있지만, 왼쪽(`client=`)은 함수가 받는 인자 이름이고 오른쪽(`client`)은
내가 만든 변수 이름입니다.

## import

다른 파일(모듈)에 있는 코드를 지금 파일에서 쓸 수 있게 가져오는
문장입니다.

```python
from midas_nx import MidasClient, Product
from midas_nx.db.node_element import Node
```

`midas_nx` 패키지 안의 `MidasClient`와 `Product`를, `midas_nx.db.node_element`
안의 `Node`를 가져온다는 뜻입니다. 이 줄이 없으면 `MidasClient`니
`Node`니 하는 이름을 파이썬이 전혀 모릅니다 — 그래서 모든 예제 맨 위에
있습니다.

## if 문

조건에 따라 다른 코드를 실행합니다. 조건 뒤에 `:`를 쓰고, 실행할 코드는
한 칸 들여씁니다(보통 스페이스 4칸).

```python
if n["Z"] > 3.0:
    print("3m보다 높은 노드입니다")
```

[절점/요소 조회 Recipe](../recipes/read-nodes-and-elements.md)의
`if e["TYPE"] == "BEAM"`도 같은 형태 — "왼쪽과 오른쪽이 같으면"이라는
뜻으로, 비교에는 `==`(같다)를 쓰고 `=`(대입)와 다르다는 점만 주의하세요.

## for 문

여러 개를 하나씩 순서대로 처리합니다.

```python
for nid, n in nodes.items():
    print(f"#{nid}: {n}")
```

`nodes`가 딕셔너리일 때 `.items()`는 "(키, 값)" 쌍을 하나씩 꺼내주고,
`for nid, n in ...`은 그 쌍을 각각 `nid`(키)와 `n`(값)이라는 이름에
담아 반복합니다. [절점 조회 Recipe](../recipes/read-nodes-and-elements.md)의
`for nid, n in high_nodes.items(): print(...)`가 그대로 이 형태입니다.

## (참고) 한 줄로 필터링하기

Recipe 코드에는 이런 줄도 나옵니다.

```python
high_nodes = {nid: n for nid, n in nodes.items() if n["Z"] > 3.0}
```

이건 위의 `for` + `if`를 한 줄로 압축한 것("딕셔너리 컴프리헨션")입니다.
읽는 순서는 " `nodes.items()`의 각 `(nid, n)`에 대해, `n["Z"] > 3.0`이면,
`{nid: n}`을 결과에 넣어라"입니다. 처음엔 낯설 수 있지만, 위 `for` 문과
정확히 같은 결과를 만든다는 것만 알면 Recipe 코드를 읽는 데는
충분합니다. 직접 쓸 때는 평범한 `for` + `if`로 풀어써도 전혀 문제없습니다.

## try/except

코드가 실패할 수 있는 부분을 감싸서, 실패해도 프로그램이 그냥 멈추지
않고 원하는 대로 대응하게 합니다.

```python
from midas_nx import MidasAPIError

try:
    nodes = Node.items(client=client)
except MidasAPIError as e:
    print(f"조회 실패: {e}")
```

`midas-nx`가 일으키는 오류는 전부 `MidasAPIError`의 하위 종류이므로
(`MidasConnectionError`, `MidasAuthError` 등), `except MidasAPIError`
하나로 이 SDK가 낼 수 있는 오류를 전부 잡을 수 있습니다. 다만 [AI 코딩
안전 시작 가이드](../ai-coding/safe-start.md)가 강조하듯, timeout으로
실패했다고 무조건 재시도하지는 마세요 — 요청이 실제로는 반영됐을 수도
있습니다.

## 파일과 환경변수

`quickstart.md`의 예제는 편의상 `mapi_key="..."`처럼 키를 코드에 직접
씁니다. 다음 단계로 넘어가면(특히 이 파일을 다른 사람과 공유하거나
Git에 올릴 때) 키를 코드 밖, **환경변수**에 두고 코드에서는 그 이름만
참조하는 방법을 씁니다.

```python
import os

mapi_key = os.environ["MIDAS_MAPI_KEY"]
client = MidasClient(mapi_key=mapi_key, product=Product.GEN)
```

이렇게 하면 스크립트 파일 자체에는 실제 키 값이 전혀 남지 않습니다.
환경변수는 명령 프롬프트에서 `set MIDAS_MAPI_KEY=여기에_키`(Windows,
현재 창에서만 유효) 또는 시스템 환경변수 설정으로 지정합니다.

## 다음

- [시작 가이드](quickstart.md)로 돌아가 4단계부터 이어서 진행하세요.
- [Recipes](../recipes/index.md) — 여기서 배운 문법이 실제로 어떻게
  쓰이는지 완성된 예제로 확인해보세요.
- 더 깊이 배우고 싶다면 [파이썬 공식 튜토리얼](https://docs.python.org/ko/3/tutorial/)
  (한국어)을 참고하세요 — 이 페이지는 그 전체를 대신하지 않습니다.
