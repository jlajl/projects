# AnythingLLM 文档上传页

一个单文件网页（`index.html`），对接本机 AnythingLLM 的 Document API：读取第一个工作区 →
选择本地文件 → 上传并**直接嵌入（addToWorkspaces）**，页面展示加载 / 成功 / 失败三态。

## 前置条件

| 项 | 要求 |
|---|---|
| AnythingLLM | 运行在 `http://localhost:3001`，且已配置可用的 LLM 后端 |
| 浏览器 | 支持 fetch / FormData 的现代浏览器（Chrome / Edge 均可） |
| Python | 仅用于起本地静态服务；`python 3.9+` |

AnythingLLM 的 API Key 可在 AnythingLLM → Settings → API Keys 中生成。

## 配置（密钥不落代码）

1. 复制 `config.example.js` 为 `config.js`；
2. 填入自己的值：

```js
window.ANYTHINGLLM_CONFIG = {
  apiBase: "http://localhost:3001/api",
  apiKey: "<你的 API Key>"
};
```

`config.js` 已被仓库根目录 `.gitignore` 忽略，真实密钥不会进入版本库；`index.html` 中不含任何密钥。

| 字段 | 说明 | 默认 |
|---|---|---|
| `apiBase` | AnythingLLM 的 API 根地址 | `http://localhost:3001/api` |
| `apiKey` | API Key，请求时以 `Authorization: Bearer` 发送 | 空（为空时页面直接提示"未配置 API Key"） |

## 启动与验证

```bash
cd AnythingLLMServer
python -m http.server 8000
# 浏览器打开 http://127.0.0.1:8000/index.html
```

验证步骤：

1. 页面顶部应显示"第一个工作区：<名称>（slug: …）"——来自 `GET /api/v1/workspaces`，不是写死的；
2. 选择任意 `.txt` / `.md` / `.pdf` 文件，点"上传并嵌入"；
3. 成功后显示标题、位置、词数、Token 估算（来自 `POST /api/v1/document/upload` 的返回）。

## 用到的接口

| 方法 | 端点 | 用途 |
|---|---|---|
| GET | `/v1/workspaces` | 取第一个工作区（列表来自接口） |
| POST | `/v1/document/upload` | 上传文件，`addToWorkspaces=<slug>` 触发嵌入 |

## 失败场景

| 现象 | 原因 | 处理 |
|---|---|---|
| "获取工作区失败：未配置 API Key" | 缺 `config.js` 或未填 `apiKey` | 按上文配置 |
| "获取工作区失败：…"（其它） | AnythingLLM 未启动 / 端口不是 3001 | 启动 AnythingLLM 或改 `apiBase` |
| "上传失败：HTTP 401" | API Key 无效 | 重新生成 Key |
| "上传失败：HTTP 404" | 工作区 slug 与后端不一致 | 刷新页面重新拉取 |
