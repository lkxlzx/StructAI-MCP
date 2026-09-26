# midas-nx

Typed JavaScript/TypeScript SDK for the **MIDAS NX Open API**, covering
**MIDAS Civil NX** and **MIDAS Gen NX**. It drives the product you already
use — read a model, build one, run an analysis, pull a result table — from
Node.js, with every endpoint and payload typed.

The npm and Python packages are maintained together from the same reviewed
endpoint inventory in the
[MIDAS-API-NX-SDK repository](https://github.com/Dennis5882/MIDAS-API-NX-SDK).

## Before you start

Three things, none of which this package can do for you:

1. **MIDAS Gen NX or Civil NX must be running**, with the Open API connected.
   Calls go through MIDAS IT's relay to that machine — which is often not the
   machine running your code.
2. **You need a MAPI key.** It is issued in the product, not here.
   [Step 3 of the npm quickstart](https://dennis5882.github.io/MIDAS-API-NX-SDK/npm/quickstart/#step-3-get-a-mapi-key)
   shows exactly where to click; the same screen gives you the Base URL.
3. **Node.js 18 or newer.**

```bash
npm install midas-nx
```

The package has no runtime dependencies, and nothing in it needs Python
installed. The `midas-nx` package on PyPI is the separate Python SDK for the
same API, not a requirement of this one.

## Your first script

```ts
import { MidasClient, resources } from "midas-nx";

const client = new MidasClient({
  mapiKey: process.env.MIDAS_MAPI_KEY,
  product: "gen", // "gen" or "civil"
});

console.log(await client.verifyConnection());

const nodes = await resources.db.nodeElement.node.items(client);
console.log(`${Object.keys(nodes).length} node(s) in the current model.`);
```

**Risk level: 1 — read-only**
(see [Risk levels](https://dennis5882.github.io/MIDAS-API-NX-SDK/safety/#risk-levels)).
It cannot create, change, or delete anything, so it is safe to run against a
real model.

`MIDAS_MAPI_KEY` and `MIDAS_BASE_URL` may also be supplied as environment
variables in Node.js. Browser applications should pass credentials explicitly
and must not expose a long-lived API key in public client code.

## Where to go next

| | |
| --- | --- |
| Runnable scripts, read-only first | [`examples/javascript/`](https://github.com/Dennis5882/MIDAS-API-NX-SDK/tree/main/examples/javascript/) |
| **Read before you write anything** — what can discard work or crash the product | [Safety guide](https://dennis5882.github.io/MIDAS-API-NX-SDK/safety/) |
| Installing, getting a key, first script, step by step | [npm quickstart](https://dennis5882.github.io/MIDAS-API-NX-SDK/npm/quickstart/) — also in [한국어](https://dennis5882.github.io/MIDAS-API-NX-SDK/npm/quickstart-ko/) and [繁體中文](https://dennis5882.github.io/MIDAS-API-NX-SDK/npm/quickstart-zh-tw/) |
| Letting an AI assistant write the code for you | [Safe start](https://dennis5882.github.io/MIDAS-API-NX-SDK/ai-coding/safe-start/) · [context pack](https://dennis5882.github.io/MIDAS-API-NX-SDK/ai-coding/context-pack/) |
| Which endpoints exist and how far each is verified | [ROADMAP.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/ROADMAP.md) |
| Full documentation | [Documentation site](https://dennis5882.github.io/MIDAS-API-NX-SDK/) |

## API

DB endpoints are grouped by the same domain structure as the official manual.
Payloads and supported products/methods are typed and attached to each
resource.

The calls below **change the model**. Get a read-only script working first.

```ts
import { MidasClient, resources } from "midas-nx";

const client = new MidasClient({ mapiKey: "...", product: "civil" });
const node = resources.db.nodeElement.node;

await node.create({ 1: { X: 0, Y: 0, Z: 0 } }, client);
const nodes = await node.items(client);
await node.delete([1], client); // one DELETE request per ID
```

Whole-table deletion requires an explicit confirmation, because the API's own
delete-by-body form empties the table and takes attached records with it:

```ts
await resources.db.nodeElement.node.deleteAll({ confirm: true, client });
```

Document, operation, and view endpoints use camelCase names while preserving
the official request field names inside their typed argument objects.

```ts
import { doc, operations } from "midas-nx";

await doc.save({ client });
await operations.view.setAngle({ HORIZONTAL: 30, VERTICAL: 15 }, { client });
```

Result tables use an options object. The SDK translates its camelCase option
names into MIDAS's uppercase wire keys and does not rely on the unstable
top-level response key.

```ts
import { tables, unwrapTable } from "midas-nx";

const raw = await tables.result1.getReactionTable({
  loadCaseNames: ["DL(ST)"],
  nodeElements: { keys: [1, 2] },
  client,
});
const table = unwrapTable(raw);
```

Advanced users can call any command directly with `client.request(...)` or
the default-client helper `midasApi(...)`.

## Safety notes

This SDK drives a live engineering application. A `200` response does not
always mean success.

- File paths are resolved on the computer running MIDAS NX, which may not be
  the computer running this code. A path that does not exist there raises a
  dialog *there* and blocks the session, while the HTTP call still answers
  like a success.
- A request timeout only stops the SDK from waiting. It does not roll back an
  analysis or design operation already accepted by MIDAS NX.
- `doc.newProject()` can discard work, open a modal product dialog, or require
  the MIDAS NX process to be restarted. Do not use it unattended on a model
  that matters.
- Design and result-table functions carry the live-verification warnings in
  their TypeScript JSDoc. Read what your editor shows you before calling an
  operation against a real model.
- Per-ID deletion is deliberately sequential. Whole-table deletion remains
  blocked unless `confirm: true` is passed explicitly.

The [safety guide](https://dennis5882.github.io/MIDAS-API-NX-SDK/safety/) has
the full list, including the calls that have crashed a product outright.

## Project status

Built by a MIDAS IT employee, from hands-on verification against real Gen NX
and Civil NX sessions. It is an **employee-led open-source project — not an
officially released or supported MIDAS IT product**. Issues with this SDK go
to [GitHub Issues](https://github.com/Dennis5882/MIDAS-API-NX-SDK/issues);
questions about the products, licensing, or the Open API service itself go to
MIDAS IT's official support channels. For anything else — questions, feedback,
or just getting in touch — the author is Dennis, on
[LinkedIn](https://www.linkedin.com/in/dennis58).

### 한국어

`midas-nx`는 MIDAS Civil NX와 MIDAS Gen NX의 Open API를 위한 타입 지원
JavaScript/TypeScript SDK입니다. PyPI의 Python 패키지와 동일한 검토 완료
엔드포인트 목록을 기준으로 함께 유지보수합니다. 마이다스아이티 재직자가 실제
제품 검증 경험을 바탕으로 개발·관리하는 **직원 주도형 오픈소스 프로젝트**이며,
마이다스아이티가 공식적으로 출시·지원하는 제품은 아닙니다. SDK 자체의 문제는
[GitHub Issues](https://github.com/Dennis5882/MIDAS-API-NX-SDK/issues)로,
제품·라이선스·Open API 서비스 자체에 대한 문의는 마이다스아이티 공식 지원
채널로 부탁드립니다. 그 밖의 질문이나 피드백, 그냥 연락을 원하시면 제작자
Dennis의 [LinkedIn](https://www.linkedin.com/in/dennis58)으로 연락 주셔도 됩니다.

시작하려면 MAPI 키가 필요합니다 —
[한국어 npm 퀵스타트](https://dennis5882.github.io/MIDAS-API-NX-SDK/npm/quickstart-ko/#3-mapi)에
발급 위치가 나와 있습니다. 모델을 변경하는 코드를 쓰기 전에
[안전 가이드](https://dennis5882.github.io/MIDAS-API-NX-SDK/safety/)를 먼저
읽어보시길 권합니다.

### 繁體中文

`midas-nx` 是 MIDAS Civil NX 與 MIDAS Gen NX Open API 的型別化
JavaScript/TypeScript SDK，與 PyPI 上的 Python 套件依據同一份經審核的端點清單
共同維護。由 MIDAS IT 員工根據實際產品驗證經驗開發維護，屬於**員工自主的開源
專案**，並非 MIDAS IT 官方發布或提供技術支援的產品。SDK 本身的問題請至
[GitHub Issues](https://github.com/Dennis5882/MIDAS-API-NX-SDK/issues)；產品、
授權或 Open API 服務本身的問題，請洽 MIDAS IT 官方支援管道。其他問題、意見回饋
或想直接聯繫，歡迎透過作者 Dennis 的
[LinkedIn](https://www.linkedin.com/in/dennis58)。

開始前需要 MAPI 金鑰 —
[繁體中文 npm 快速入門](https://dennis5882.github.io/MIDAS-API-NX-SDK/npm/quickstart-zh-tw/#3-mapi)
說明取得位置。在撰寫會變更模型的程式碼之前，請先閱讀
[安全指南](https://dennis5882.github.io/MIDAS-API-NX-SDK/safety/)。

### 简体中文

`midas-nx` 是 MIDAS Civil NX 与 MIDAS Gen NX Open API 的类型化
JavaScript/TypeScript SDK，与 PyPI 上的 Python 包依据同一份经审核的端点清单
共同维护。由 MIDAS IT 员工基于实际产品验证经验开发维护，属于**员工自主的开源
项目**，并非 MIDAS IT 官方发布或提供技术支持的产品。SDK 本身的问题请提交至
[GitHub Issues](https://github.com/Dennis5882/MIDAS-API-NX-SDK/issues)；产品、
授权或 Open API 服务本身的问题，请联系 MIDAS IT 官方支持渠道。其他问题、反馈
或想直接联系，欢迎通过作者 Dennis 的
[LinkedIn](https://www.linkedin.com/in/dennis58)。

开始前需要 MAPI 密钥 —
[npm 快速入门指南](https://dennis5882.github.io/MIDAS-API-NX-SDK/npm/quickstart-zh-tw/#3-mapi)
（繁体中文版）说明获取位置。在编写会修改模型的代码之前，请先阅读
[安全指南](https://dennis5882.github.io/MIDAS-API-NX-SDK/safety/)。

## Releases

- [npm package changelog](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/packages/typescript/CHANGELOG.md)
- [GitHub Releases](https://github.com/Dennis5882/MIDAS-API-NX-SDK/releases) — npm releases use `js-v*` tags

Licensed under the MIT License.
