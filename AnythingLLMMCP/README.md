# AnythingLLM MCP Server

通过 MCP 协议访问本机 AnythingLLM，向第一个工作区提问并返回 AI 回答。

## 前置条件

- Python 3.10+
- AnythingLLM 运行在 `http://localhost:3001`
- AnythingLLM 已配置可用的 LLM 后端（如 LMStudio、OpenAI 等）

## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动 MCP 服务器

```bash
python server.py
```

服务启动后监听 `http://127.0.0.1:8001/mcp`，使用 Streamable HTTP 传输，支持 MCP 协议 2026-07-28。

## 停止 MCP 服务器

在运行 `python server.py` 的终端中按 `Ctrl+C` 即可停止服务。

## 项目级 MCP 配置

项目根目录的 `.mcp.json` 已配置好，内容如下：

```json
{
  "mcpServers": {
    "anythingllm": {
      "url": "http://127.0.0.1:8001/mcp"
    }
  }
}
```

Trae 会自动读取此配置。确保先启动 MCP 服务器，再在 Trae 中使用 AI 对话。

## 可用工具

| 工具 | 说明 |
|------|------|
| `chat` | 向 AnythingLLM 第一个工作区提问，返回 AI 回答及来源信息 |

参数：`message`（字符串）— 要提问的内容。
