# midas-nx JavaScript / TypeScript 퀵스타트 (한국어)

MIDAS Gen NX / Civil NX를 Node.js에서 다루려는 엔지니어를 위한 안내입니다.
Node 설치부터 첫 읽기 전용 스크립트 실행까지 순서대로 따라가면 한 번에
끝낼 수 있습니다.

> `midas-nx`는 마이다스아이티 재직자가 실제 제품·API 검증 경험을 바탕으로
> 개발·관리하는 **직원 주도형 오픈소스 프로젝트**이며, 마이다스아이티가
> 공식적으로 출시·지원하는 제품은 아닙니다. SDK나 이 문서의 문제는
> [GitHub Issues](https://github.com/Dennis5882/MIDAS-API-NX-SDK/issues)로
>알려주세요. 마이다스아이티 제품 지원 대상이 아닙니다.

> Python을 쓰신다면 [한국어 퀵스타트](../ko/quickstart.md)가 PyPI 패키지용
> 같은 안내이며, 프로그래밍 경험이 전혀 없다고 가정하고 쓰여 있습니다.

## 시작하기 전에

- MIDAS Gen NX 또는 Civil NX가 설치되어 있고 라이선스가 유효할 것
- 인터넷 연결 — SDK는 마이다스의 중계 서버를 거칩니다
- **제품이 접근 가능한 어느 PC에서 실행 중일 것.** 코드를 돌리는 PC와 같을
  필요는 없습니다. [5단계](#5)를 보세요.

## 1단계: Node.js 설치

`midas-nx`는 **Node.js 18 이상**이 필요합니다. 현재 버전을 확인하세요.

```bash
node --version
```

`v18`보다 낮거나 오류가 나면 https://nodejs.org/ 에서 LTS 버전을 설치하세요.
공식 설치 프로그램, `nvm`, `fnm`, Homebrew, `winget` 무엇이든 괜찮습니다.

## 2단계: 프로젝트 만들고 midas-nx 설치

```bash
mkdir midas-scripts
cd midas-scripts
npm init -y
npm install midas-nx
```

이 패키지는 **런타임 의존성이 없고**, Python 설치도 필요 없습니다. (PyPI의
`midas-nx`는 같은 API를 다루는 별도의 Python SDK이며 이 패키지의
요구사항이 아닙니다.)

TypeScript 선언이 함께 배포되므로, 에디터가 모든 엔드포인트와 payload
필드를 자동완성해 줍니다. `@types/` 패키지를 따로 설치할 필요가 없습니다.

## 3단계: MAPI 키 발급

`MAPI-Key`는 이 SDK가 MIDAS Gen NX / Civil NX와 통신할 때 쓰는 인증
키입니다. npm이 아니라 **MIDAS Gen NX(또는 Civil NX) 프로그램 안에서**
발급받습니다.

1. MIDAS Gen NX(또는 Civil NX)를 실행합니다.
2. 상단 메뉴에서 **Apps** → **API Settings**를 엽니다.
3. 화면에 **Base URL**과 **MAPI-Key**가 보입니다. 각각 옆의 **Copy**
   버튼으로 복사하세요.
4. **Connected**를 클릭합니다. 성공하면 Status가 **Connected**로 바뀌며,
   이것이 Open API가 실제로 활성화됐다는 확인입니다.

> 키를 새로 받고 싶다면(예: 유출이 의심되면) 옆의 **Refresh**를 누르세요.
> 기존 키는 즉시 무효화됩니다.

> ⚠️ **유효한 동안에는 비밀번호처럼 다루세요.** 파일에 직접 적기보다
> 환경 변수에 두고, 커밋하거나 공개 이슈에 붙여넣거나 키가 보이는
> 스크린샷을 공유하지 마세요.

> 🌏 **어느 지역 서버인지 추측할 필요 없습니다.** 같은 화면의 **Base URL**을
> 쓰면 중국 전용 서버를 포함해 어느 지역이든 맞습니다. 기본 전역 중계
> 주소(`moa-engineers.midasit.com`)와 다르면
> `new MidasClient({ ... })`에 `baseUrl: "복사한 값"`을 넘기세요.

## 4단계: 첫 스크립트 작성·실행 (읽기 전용)

**위험도 1 — 읽기 전용** ([위험도 설명](../safety.md#risk-levels)).

2단계에서 만든 폴더에 `first-script.mjs`로 저장하세요. `.mjs` 확장자를 쓰면
별도 설정 없이 `import`와 최상위 `await`를 쓸 수 있습니다.

```js
import { MidasClient, resources } from "midas-nx";

// Civil NX를 쓰신다면 product: "civil"로 바꾸세요.
const client = new MidasClient({
  mapiKey: process.env.MIDAS_MAPI_KEY,
  product: "gen",
});

console.log(await client.verifyConnection());

const nodes = await resources.db.nodeElement.node.items(client);
console.log(`Connected. Found ${Object.keys(nodes).length} node(s) in the current model.`);
```

키를 환경 변수에 넣고 실행합니다.

```powershell
# Windows PowerShell
$env:MIDAS_MAPI_KEY = "3단계에서_복사한_키"
node first-script.mjs
```

```bash
# macOS / Linux
export MIDAS_MAPI_KEY="3단계에서_복사한_키"
node first-script.mjs
```

다음과 비슷한 출력이 나오면 성공입니다.

```
{ status: 'connected', keyVerified: true }
Connected. Found 3 node(s) in the current model.
```

(노드 수는 현재 열려 있는 모델에 따라 다릅니다. 빈 프로젝트라면 `0`이
정상입니다.)

**이 스크립트는 읽기만 합니다.** 어떤 프로젝트에 대고 실행하든 모델을
생성·수정·삭제하지 않으므로, 실제 작업 파일에 시도해도 안전합니다.

### 잘 안 될 때

- **`MidasConnectionError`**: Gen NX / Civil NX가 실행 중이고 Open API가
  연결돼 있는지 확인하세요. 이 SDK의 오류 메시지는 확인할 항목을 알려주는
  `(Hint: ...)`로 끝납니다.
- **`MidasAuthError`**: 3단계의 키가 프로세스까지 전달됐는지 확인하세요.
  `console.log(process.env.MIDAS_MAPI_KEY?.length)`가 `undefined`가 아니라
  숫자를 찍어야 합니다 — 새 터미널 창은 이전 창에서 설정한 변수를 물려받지
  않습니다. 제품을 재시작하면 키가 바뀔 수도 있습니다.
- **`ERR_MODULE_NOT_FOUND`**: `node_modules`가 있는 폴더가 아닌 곳에서
  실행하고 있습니다. 먼저 프로젝트 폴더로 `cd` 하세요.
- **사내 방화벽 환경**: IT 담당자에게 전달할 포트·주소 정보는
  [연결 문제 해결](../safety.md#connectivity-troubleshooting)에 있습니다.

## 5단계: 어느 PC와 통신하는지 알아두기 {#5}

호출은 마이다스 중계 서버를 거쳐 **MIDAS NX가 돌아가는 PC**로 갑니다. 스크립트를
실행하는 PC와 다른 경우가 많고, 이게 생각보다 중요합니다.

- **모든 파일 경로는 MIDAS NX PC 기준으로 해석됩니다.** export 경로,
  `doc.saveAs()`, `doc.openProject()`, 보고서·이미지 경로 전부입니다. 그
  PC에 없는 경로를 주면 **그쪽에서** 대화상자가 떠서 세션이 멈추는데,
  HTTP 호출은 성공한 것처럼 응답합니다.
- **멈춘 세션은 `verifyConnection()`으로 보이지 않습니다.** 제품에 모달
  대화상자가 떠 있어도 중계 서버는 "connected"라고 답하고, 실제 호출만
  전부 타임아웃납니다.

## 6단계: 모델 변경 (선택 — 여기서부터 쓰기입니다)

이 아래는 모델을 바꿀 수 있습니다. 먼저 [안전 가이드](../safety.md)를
읽어주세요. 요약은 아래에 있습니다.

DB 엔드포인트는 `resources` 트리에 있고, 레코드 id로 키잉합니다.

```js
import { MidasClient, resources } from "midas-nx";

const client = new MidasClient({ product: "gen" });
const node = resources.db.nodeElement.node;

await node.create({ 1: { X: 0, Y: 0, Z: 0 } }, client);
const nodes = await node.items(client);
await node.delete([1], client); // id 하나당 DELETE 요청 한 번
```

payload 안의 필드명은 API 매뉴얼에 적힌 그대로의 대문자 wire 이름입니다.
에디터가 자동완성해 줍니다.

본격적으로 쓰기 전에 몸에 익혀야 할 세 가지입니다.

1. **`doc.newProject()`는 저장하지 않은 작업을 버립니다.** 열려 있는
   문서의 작업 전부이며, 내 스크립트와 무관한 것까지 포함합니다. 중요한
   모델에 대고 사람 없이 실행하지 마세요.
2. **`deleteAll()`은 테이블 전체를 비웁니다.** 그래서 `{ confirm: true }`를
   명시적으로 요구합니다. 특정 레코드는 `delete(ids, client)`를 쓰세요.
3. **타임아웃은 롤백이 아닙니다.** HTTP 호출이 포기한 뒤에 작업이 반영될
   수 있습니다. 쓰기가 타임아웃났을 때 자동 재시도하지 말고, 모델 상태를
   먼저 확인하세요.

## 다음 단계

- [실행 가능한 예제](https://github.com/Dennis5882/MIDAS-API-NX-SDK/tree/main/examples/javascript/)
  — 읽기 전용부터 시작해 모델 생성, 하중조합, 풍하중까지. 각 파일 상단에
  위험도가 적혀 있습니다.
- [안전 가이드](../safety.md) — 위험도 등급과, 실제로 제품을 다운시킨
  호출들.
- [AI에게 코드를 맡기기](../ai-coding/safe-start.md) — 사용자가 아니라
  어시스턴트에게 읽히는
  [컨텍스트 팩](../ai-coding/context-pack.md#javascript-and-typescript) 포함.
- [ROADMAP.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/ROADMAP.md)
  — 모든 엔드포인트와 각각이 실제 제품에 대해 어디까지 검증됐는지.
