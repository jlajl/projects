# AnythingLLM MCP Server

把本机 AnythingLLM 的能力封装成 MCP 工具，供 Claude Desktop / Trae / MCP Inspector 等客户端调用。
传输方式为 **Streamable HTTP**，默认监听 `http://127.0.0.1:8001/mcp`。

## 前置条件

- Python 3.10+
- `mcp`（Python SDK，见 `requirements.txt`）与 `httpx`
- AnythingLLM 运行在 `http://localhost:3001`，并已配置可用的 LLM 后端
- 在 AnythingLLM 中生成 API Key（Settings → API Keys）

## 配置（密钥走环境变量，不写进代码）

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `ANYTHINGLLM_URL` | AnythingLLM 服务地址（末尾自动去 `/`） | `http://localhost:3001` |
| `ANYTHINGLLM_API_KEY` | API Key，**必填**；为空时任何工具调用都会返回明确提示 | 无 |

```bash
# PowerShell
$env:ANYTHINGLLM_URL="http://localhost:3001"
$env:ANYTHINGLLM_API_KEY="<你的 API Key>"

# bash
export ANYTHINGLLM_URL=http://localhost:3001
export ANYTHINGLLM_API_KEY=<你的 API Key>
```

`.env.example` 给出了两个字段的模板；真实的 `.env`、密钥文件已被 `.gitignore` 忽略，**不要提交**。

## 启动与停止

```bash
pip install -r requirements.txt
python server.py          # 启动后监听 127.0.0.1:8001/mcp
```

在运行 `python server.py` 的终端按 `Ctrl+C` 停止。

客户端侧的项目级配置（`.mcp.json`，Trae / Claude 可直接读）：

```json
{
  "mcpServers": {
    "anythingllm": {
      "url": "http://127.0.0.1:8001/mcp"
    }
  }
}
```

## 可用工具

| 工具 | 说明 | 依赖的 AnythingLLM 接口 |
|---|---|---|
| `chat(message)` | 向第一个工作区提问，返回回答正文与来源片段 | `GET /api/v1/workspaces`、`POST /api/v1/workspace/{slug}/chat` |
| `list_documents()` | 列出第一个工作区已嵌入的文档：标题、字数、预估 token、发布时间 | `GET /api/v1/workspace/{slug}`、`GET /api/v1/documents` |
| `upload_document(file_path)` | 上传本地文件到第一个工作区并立即触发向量化嵌入 | `POST /api/v1/document/upload`（`addToWorkspaces=<slug>`） |

参数：
- `chat`：`message`（字符串，要提问的内容）。
- `list_documents`：无参数，返回文本清单；工作区为空时返回"（工作区中暂无嵌入文档）"。
- `upload_document`：`file_path`（本地文件路径）；不存在时直接返回"错误：文件不存在"，上传不成功时返回后端原始错误。

## 示例调用

MCP Inspector：

```bash
npx @modelcontextprotocol/inspector
# 传输选 Streamable HTTP，填 http://127.0.0.1:8001/mcp，连接后可直接列出/调用工具
```

直接打协议（确认服务在跑）：

```bash
curl -X POST http://127.0.0.1:8001/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}'
```

## 失败场景

| 现象 | 原因 | 处理 |
|---|---|---|
| 工具返回"未配置 ANYTHINGLLM_API_KEY…" | 环境变量未设置 | 按上文设置后重启服务 |
| 工具返回 `401` | Key 无效或已轮换 | 重新生成 Key |
| 返回"没有可用工作区" | AnythingLLM 里还没有工作区 | 先在 AnythingLLM 建一个工作区 |
| `upload_document` 返回"错误：文件不存在" | 路径写错或不在本机 | 换成绝对路径再试 |
| `upload_document` 返回 HTTP 413 | 文件超过后端上传限制 | 拆分或换小文件 |
| 客户端连不上 / 立刻断开 | 服务未启动，或端口不是 8001 | 确认 `python server.py` 在跑 |

## 目录说明

| 文件 | 说明 |
|---|---|
| `server.py` | MCP Server 主体（工具注册 + HTTP 传输） |
| `.mcp.json` | 客户端侧的连接配置 |
| `.env.example` | 环境变量模板（不含真实密钥） |
| `headers.txt` / `init_resp.txt` | 早期手工调试留下的原始 HTTP 报文，仅作排查参考，非运行所需 |
