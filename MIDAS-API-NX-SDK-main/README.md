# midas-nx

Unified Python and JavaScript/TypeScript SDKs for the **MIDAS NX Open API** —
both packages cover **MIDAS Civil NX** and **MIDAS Gen NX** from the same
reviewed endpoint inventory.

Either one needs MIDAS Gen NX or Civil NX running with the Open API connected,
and a **MAPI key**. The key is issued in the product, not here — step 3 of the
[Python](https://dennis5882.github.io/MIDAS-API-NX-SDK/en/quickstart/#step-3-get-a-mapi-key) or
[npm](https://dennis5882.github.io/MIDAS-API-NX-SDK/npm/quickstart/#step-3-get-a-mapi-key) quickstart shows where to
click, and the same screen gives you the Base URL.

## Python (PyPI)

```bash
pip install midas-nx
```

```python
from midas_nx import MidasClient, Product
from midas_nx.db.node_element import Node

client = MidasClient(mapi_key="your-mapi-key-here", product=Product.GEN)
print(client.verify_connection())
print(f"{len(Node.items(client=client))} node(s) in the current model.")
```

## JavaScript / TypeScript (npm)

```bash
npm install midas-nx
```

```ts
import { MidasClient, resources } from "midas-nx";

const client = new MidasClient({
  mapiKey: process.env.MIDAS_MAPI_KEY,
  product: "gen",
});

await client.verifyConnection();
const nodes = await resources.db.nodeElement.node.items(client);
console.log(`${Object.keys(nodes).length} node(s) in the current model.`);
```

**Risk level: 1 — read-only** (see [Risk levels](https://dennis5882.github.io/MIDAS-API-NX-SDK/safety/#risk-levels)).
It can't create, change, or delete anything, so it's safe to run against a
real model.

More examples, including ones that build a model:
[`examples/python/`](https://github.com/Dennis5882/MIDAS-API-NX-SDK/tree/main/examples/python/)
(four, up to a load combination and a KDS wind load) and
[`examples/javascript/`](https://github.com/Dennis5882/MIDAS-API-NX-SDK/tree/main/examples/javascript/)
(the read-only one and the model-building one, matching their Python
namesakes payload for payload). For the npm API and safety notes, see the
[`packages/typescript` guide](https://github.com/Dennis5882/MIDAS-API-NX-SDK/tree/main/packages/typescript).
Full guide, safety notes, and API reference: **[Documentation site](https://dennis5882.github.io/MIDAS-API-NX-SDK/)**.

---

## English

Built by a MIDAS IT employee, from hands-on verification against real Gen NX
and Civil NX sessions. It's an **employee-led open-source project — not an
officially released or supported MIDAS IT product**. Issues with this SDK go
to [GitHub Issues](https://github.com/Dennis5882/MIDAS-API-NX-SDK/issues);
questions about the products, licensing, or the Open API service itself go to
MIDAS IT's official support channels. For anything else — questions, feedback,
or just getting in touch — the author is Dennis, on [LinkedIn](https://www.linkedin.com/in/dennis58).

The repository maintains both the Python package on PyPI and the typed
JavaScript/TypeScript package on npm. **New to Python?**
[docs/en/quickstart.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/docs/en/quickstart.md)
walks through installing Python and running your first script.

## 한국어

`midas-nx`는 MIDAS Civil NX와 MIDAS Gen NX의 Open API를 Python(PyPI)과
JavaScript/TypeScript(npm) 패키지로 제공하는 SDK입니다. 두 패키지는 동일한
검토 완료 엔드포인트 목록을 기준으로 함께 유지보수합니다. 마이다스아이티
재직자가 실제 제품 검증 경험을
바탕으로 개발·관리하는 **직원 주도형 오픈소스 프로젝트**이며, 마이다스아이티가
공식적으로 출시·지원하는 제품은 아닙니다. SDK 자체의 문제는
[GitHub Issues](https://github.com/Dennis5882/MIDAS-API-NX-SDK/issues)로,
제품·라이선스·Open API 서비스 자체에 대한 문의는 마이다스아이티 공식
지원 채널로 부탁드립니다. 그 밖의 질문이나 피드백, 그냥 연락을 원하시면
제작자 Dennis의 [LinkedIn](https://www.linkedin.com/in/dennis58)으로 연락 주셔도 됩니다.

**Python이나 프로그래밍이 처음이신 구조 엔지니어**는
[한국어 퀵스타트 가이드](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/docs/ko/quickstart.md)에서
설치부터 첫 스크립트 실행까지 순서대로 안내받으실 수 있습니다.

## 繁體中文

`midas-nx` 將 MIDAS Civil NX 與 MIDAS Gen NX 的 Open API 提供為 Python
（PyPI）及 JavaScript/TypeScript（npm）套件，兩者依據同一份經審核的端點清單
共同維護。由 MIDAS IT 員工根據實際產品驗證經驗開發維護，屬於
**員工自主的開源專案**，並非 MIDAS IT 官方發布或提供技術支援的產品。SDK
本身的問題請至 [GitHub Issues](https://github.com/Dennis5882/MIDAS-API-NX-SDK/issues)；
產品、授權或 Open API 服務本身的問題，請洽 MIDAS IT 官方支援管道。
其他問題、意見回饋或想直接聯繫，歡迎透過作者 Dennis 的 [LinkedIn](https://www.linkedin.com/in/dennis58)。

**從未寫過 Python 的結構工程師**，可參考
[繁體中文快速入門指南](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/docs/zh-tw/quickstart.md)，
內含從安裝 Python 到執行第一支腳本的完整步驟。

## 简体中文

`midas-nx` 将 MIDAS Civil NX 与 MIDAS Gen NX 的 Open API 提供为 Python
（PyPI）及 JavaScript/TypeScript（npm）包，两者依据同一份经审核的端点清单
共同维护。由 MIDAS IT 员工基于实际产品验证经验开发维护，属于
**员工自主的开源项目**，并非 MIDAS IT 官方发布或提供技术支持的产品。SDK
本身的问题请提交至 [GitHub Issues](https://github.com/Dennis5882/MIDAS-API-NX-SDK/issues)；
产品、授权或 Open API 服务本身的问题，请联系 MIDAS IT 官方支持渠道。
其他问题、反馈或想直接联系，欢迎通过作者 Dennis 的 [LinkedIn](https://www.linkedin.com/in/dennis58)。

**Python 新手**可参考
[快速入门指南](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/docs/zh-tw/quickstart.md)（繁体中文版），
了解从安装 Python 到运行第一个脚本的完整步骤。

---

## Learn more

| | |
| --- | --- |
| Full docs & API reference | [Documentation site](https://dennis5882.github.io/MIDAS-API-NX-SDK/) |
| JavaScript / TypeScript npm SDK | [packages/typescript/README.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/packages/typescript/README.md) |
| Building with an AI coding assistant instead of writing the code yourself | [Safe start](https://dennis5882.github.io/MIDAS-API-NX-SDK/ai-coding/safe-start/) |
| Pointing an AI agent at this repository | [AGENTS.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/AGENTS.md) |
| Known issues / safety notes — read before writing anything | [docs/safety.md](https://dennis5882.github.io/MIDAS-API-NX-SDK/safety/) |
| Endpoint implementation status | [ROADMAP.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/ROADMAP.md) |
| Contributing / dev setup | [CONTRIBUTING.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/CONTRIBUTING.md) |
| Reporting a security issue | [SECURITY.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/SECURITY.md) |

## License

MIT — see [LICENSE](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/LICENSE).
