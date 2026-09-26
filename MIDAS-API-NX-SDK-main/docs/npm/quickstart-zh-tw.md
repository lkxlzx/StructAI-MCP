# midas-nx JavaScript / TypeScript 快速入門（繁體中文）

本指南寫給想從 Node.js 操作 MIDAS Gen NX / Civil NX 的工程師。從安裝 Node
到執行第一支唯讀腳本，依序照做即可一次完成。

> `midas-nx` 由 MIDAS IT 員工根據實際產品與 API 驗證經驗開發維護，屬於
> **員工自主的開源專案**，並非 MIDAS IT 官方發布或提供技術支援的產品。
> SDK 或本文件的問題請至
> [GitHub Issues](https://github.com/Dennis5882/MIDAS-API-NX-SDK/issues)
> 回報，MIDAS IT 產品支援並不涵蓋本專案。

> 若您使用 Python，[繁體中文快速入門](../zh-tw/quickstart.md)是 PyPI 套件的
> 同一份指南，且假設讀者完全沒有程式經驗。

## 開始之前

- 已安裝 MIDAS Gen NX 或 Civil NX，並具備有效授權
- 網路連線 —— SDK 透過 MIDAS 的雲端中繼伺服器通訊
- **產品必須在某台您能連到的電腦上執行中。** 不一定要和跑程式的電腦相同，
  請見[第 5 步](#5)。

## 第 1 步：安裝 Node.js

`midas-nx` 需要 **Node.js 18 以上**。先確認目前版本：

```bash
node --version
```

若顯示低於 `v18` 或出現錯誤，請至 https://nodejs.org/ 安裝 LTS 版本。官方
安裝程式、`nvm`、`fnm`、Homebrew、`winget` 任一方式皆可。

## 第 2 步：建立專案並安裝 midas-nx

```bash
mkdir midas-scripts
cd midas-scripts
npm init -y
npm install midas-nx
```

本套件**沒有任何執行期相依套件**，也不需要安裝 Python。（PyPI 上的
`midas-nx` 是對應同一組 API 的獨立 Python SDK，並非本套件的必要條件。）

TypeScript 型別宣告隨套件一併發布，編輯器會自動補全每一個端點與 payload
欄位，不需要額外安裝 `@types/` 套件。

## 第 3 步：取得 MAPI 金鑰

`MAPI-Key` 是本 SDK 與 MIDAS Gen NX / Civil NX 通訊所用的驗證金鑰。它是
**在 MIDAS Gen NX（或 Civil NX）程式內**取得的，而不是從 npm。

1. 啟動 MIDAS Gen NX（或 Civil NX）。
2. 在上方選單開啟 **Apps**，點選 **API Settings**。
3. 畫面會顯示 **Base URL** 與 **MAPI-Key**，各自點旁邊的 **Copy** 複製。
4. 點選 **Connected**。成功後 Status 會切換為 **Connected**，這才確認
   Open API 確實已啟用。

> 想換新金鑰（例如懷疑外洩）？點旁邊的 **Refresh**，舊金鑰會立即失效。

> ⚠️ **金鑰有效期間請當作密碼看待。** 放在環境變數而非寫死在檔案裡，不要
> 提交到版本庫、貼到公開議題，或分享含有金鑰的截圖。

> 🌏 **不必猜測所在區域的伺服器。** 使用同一畫面上的 **Base URL** 即可，
> 包含中國的獨立伺服器在內都正確。若與 SDK 預設的全球中繼位址
> （`moa-engineers.midasit.com`）不同，請在 `new MidasClient({ ... })`
> 傳入 `baseUrl: "複製到的值"`。

## 第 4 步：撰寫並執行第一支腳本（唯讀）

**風險等級 1 —— 唯讀**（見[風險等級](../safety.md#risk-levels)）。

在第 2 步建立的資料夾中存成 `first-script.mjs`。使用 `.mjs` 副檔名即可直接
使用 `import` 與頂層 `await`，無需額外設定。

```js
import { MidasClient, resources } from "midas-nx";

// 使用 Civil NX 請改成 product: "civil"。
const client = new MidasClient({
  mapiKey: process.env.MIDAS_MAPI_KEY,
  product: "gen",
});

console.log(await client.verifyConnection());

const nodes = await resources.db.nodeElement.node.items(client);
console.log(`Connected. Found ${Object.keys(nodes).length} node(s) in the current model.`);
```

把金鑰放進環境變數後執行：

```powershell
# Windows PowerShell
$env:MIDAS_MAPI_KEY = "第3步複製到的金鑰"
node first-script.mjs
```

```bash
# macOS / Linux
export MIDAS_MAPI_KEY="第3步複製到的金鑰"
node first-script.mjs
```

出現類似以下內容即代表成功：

```
{ status: 'connected', keyVerified: true }
Connected. Found 3 node(s) in the current model.
```

（節點數量取決於您目前開啟的模型；空白專案顯示 `0` 是正常的。）

**這支腳本只會讀取資料。** 無論對哪個專案執行，都不會建立、修改或刪除模型
內容，因此對實際工作檔案執行也是安全的。

### 若執行失敗

- **`MidasConnectionError`**：確認 Gen NX / Civil NX 正在執行且 Open API
  已連線。本 SDK 的錯誤訊息結尾會有 `(Hint: ...)` 指出該檢查什麼。
- **`MidasAuthError`**：確認第 3 步的金鑰有傳進行程。
  `console.log(process.env.MIDAS_MAPI_KEY?.length)` 應印出數字而非
  `undefined` —— 新開的終端機視窗不會沿用舊視窗設定的變數。重啟產品後
  金鑰也可能改變。
- **`ERR_MODULE_NOT_FOUND`**：您在不含 `node_modules` 的資料夾執行。請先
  `cd` 進專案資料夾。
- **位於企業防火牆後**：要交給 IT 人員的連接埠與位址資訊，請見
  [連線疑難排解](../safety.md#connectivity-troubleshooting)。

## 第 5 步：清楚自己在和哪台電腦通訊 {#5}

呼叫會經由 MIDAS 中繼伺服器送到**執行 MIDAS NX 的那台電腦**，而它往往不是
執行腳本的電腦。這一點比想像中重要：

- **所有檔案路徑都以 MIDAS NX 那台電腦為準。** 匯出路徑、`doc.saveAs()`、
  `doc.openProject()`、報表與影像路徑皆然。若該路徑在那台電腦上不存在，
  對話框會跳在**那一端**並卡住工作階段，而您的 HTTP 呼叫仍會回覆得像成功
  一樣。
- **卡住的工作階段從 `verifyConnection()` 看不出來。** 產品端跳出強制對話
  框時，中繼伺服器仍回報 "connected"，只有真正的呼叫全部逾時。

## 第 6 步：修改模型（選用 —— 從這裡開始會寫入）

以下內容都可能變更模型，請先閱讀[安全指南](../safety.md)；重點摘要如下。

DB 端點掛在 `resources` 樹狀結構下，以記錄 id 為鍵：

```js
import { MidasClient, resources } from "midas-nx";

const client = new MidasClient({ product: "gen" });
const node = resources.db.nodeElement.node;

await node.create({ 1: { X: 0, Y: 0, Z: 0 } }, client);
const nodes = await node.items(client);
await node.delete([1], client); // 每個 id 各送一次 DELETE
```

payload 內的欄位名稱就是 API 手冊所寫的大寫 wire 名稱，編輯器會自動補全。

在寫更大的程式之前，有三件事值得先記牢：

1. **`doc.newProject()` 會丟棄未儲存的工作** —— 包含目前開啟文件中與您的
   腳本無關的部分。切勿在重要模型上無人看管地執行。
2. **`deleteAll()` 會清空整張表**，因此它要求明確傳入 `{ confirm: true }`。
   要刪除特定記錄請用 `delete(ids, client)`。
3. **逾時不等於回復。** HTTP 呼叫放棄等待之後，該操作仍可能完成。寫入
   逾時後切勿自動重試，請先確認模型狀態。

## 後續

- [可執行範例](https://github.com/Dennis5882/MIDAS-API-NX-SDK/tree/main/examples/javascript/)
  —— 從唯讀開始，接著是從零建模、載重組合與風載重。每個檔案開頭都標示
  風險等級。
- [安全指南](../safety.md) —— 風險等級，以及確實造成產品當掉的呼叫。
- [讓 AI 助理代寫程式](../ai-coding/safe-start.md) —— 附有寫給助理而非使用者
  的[context pack](../ai-coding/context-pack.md#javascript-and-typescript)。
- [ROADMAP.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/ROADMAP.md)
  —— 所有端點，以及各自對實際產品驗證到什麼程度。
