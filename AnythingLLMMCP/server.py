import httpx
from mcp.server.mcpserver import MCPServer

ANYTHINGLLM_URL = "http://localhost:3001"
API_KEY = "CE9VTQ6-JJFMGWX-PTWDR0A-R7F231W"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

mcp = MCPServer("AnythingLLM")
_workspace_slug = None


def _get_first_workspace_slug() -> str:
    global _workspace_slug
    if _workspace_slug is None:
        resp = httpx.get(f"{ANYTHINGLLM_URL}/api/v1/workspaces", headers=HEADERS)
        resp.raise_for_status()
        _workspace_slug = resp.json()["workspaces"][0]["slug"]
    return _workspace_slug


@mcp.tool()
def chat(message: str) -> str:
    """向 AnythingLLM 第一个工作区提问，返回 AI 回答及来源"""
    slug = _get_first_workspace_slug()
    resp = httpx.post(
        f"{ANYTHINGLLM_URL}/api/v1/workspace/{slug}/chat",
        headers=HEADERS,
        json={"message": message, "mode": "automatic"},
    )
    data = resp.json()
    if data.get("error"):
        return f"Error: {data['error']}"
    text = data.get("textResponse", "No response")
    sources = data.get("sources", [])
    if sources:
        text += "\n\n来源:\n"
        for s in sources:
            text += f"- {s.get('title', 'unknown')}: {s.get('chunk', '')[:200]}\n"
    return text


def _collect_files(node: dict) -> list[dict]:
    """递归遍历 documents 目录树，收集所有文件节点"""
    files = []
    for item in node.get("items", []):
        if item.get("type") == "folder":
            files.extend(_collect_files(item))
        elif item.get("type") == "file":
            files.append(item)
    return files


@mcp.tool()
def list_documents() -> str:
    """列出 AnythingLLM 第一个工作区中的文档，返回文档总数及每个文件的标题、字数、预估 token 等信息"""
    slug = _get_first_workspace_slug()

    # 获取工作区详情（含已嵌入文档）
    ws_resp = httpx.get(f"{ANYTHINGLLM_URL}/api/v1/workspace/{slug}", headers=HEADERS)
    ws_resp.raise_for_status()
    workspace = ws_resp.json().get("workspace", [{}])[0]
    ws_name = workspace.get("name", "未知工作区")
    embedded = {d.get("docpath"): d for d in workspace.get("documents", [])}

    # 获取全局文档库
    docs_resp = httpx.get(f"{ANYTHINGLLM_URL}/api/v1/documents", headers=HEADERS)
    docs_resp.raise_for_status()
    all_files = _collect_files(docs_resp.json().get("localFiles", {}))

    lines = [f"工作区「{ws_name}」文档总数：{len(embedded)} 个"]
    if embedded:
        lines.append("")
        for f in all_files:
            docpath = f"custom-documents/{f.get('name')}"
            if docpath in embedded:
                title = f.get("title", f.get("name", "unknown"))
                wc = f.get("wordCount", "?")
                tokens = f.get("token_count_estimate", "?")
                published = f.get("published", "")
                lines.append(f"- {title} | 字数:{wc} | 预估token:{tokens} | {published}")
    else:
        lines.append("（工作区中暂无嵌入文档）")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8001)
