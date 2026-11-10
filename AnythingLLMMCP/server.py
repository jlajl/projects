import os
from pathlib import Path

import httpx
from mcp.server.mcpserver import MCPServer

DEFAULT_URL = "http://localhost:3001"
ANYTHINGLLM_URL = os.environ.get("ANYTHINGLLM_URL", DEFAULT_URL).rstrip("/")
API_KEY = os.environ.get("ANYTHINGLLM_API_KEY", "").strip()


def _headers() -> dict[str, str]:
    """每次请求前检查配置；缺 Key 时抛出可执行的提示，而不是静默 401。"""
    if not API_KEY:
        raise RuntimeError(
            "未配置 ANYTHINGLLM_API_KEY。请先设置环境变量再启动本服务，"
            "例如 PowerShell: $env:ANYTHINGLLM_API_KEY=\"<你的密钥>\"，"
            "或参照 .env.example 填入后重新启动。"
        )
    return {"Authorization": f"Bearer {API_KEY}"}


mcp = MCPServer("AnythingLLM")
_workspace_slug = None


def _get_first_workspace_slug() -> str:
    global _workspace_slug
    if _workspace_slug is None:
        resp = httpx.get(f"{ANYTHINGLLM_URL}/api/v1/workspaces", headers=_headers())
        resp.raise_for_status()
        _workspace_slug = resp.json()["workspaces"][0]["slug"]
    return _workspace_slug


@mcp.tool()
def chat(message: str) -> str:
    """向 AnythingLLM 第一个工作区提问，返回 AI 回答及来源"""
    slug = _get_first_workspace_slug()
    resp = httpx.post(
        f"{ANYTHINGLLM_URL}/api/v1/workspace/{slug}/chat",
        headers=_headers(),
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
    ws_resp = httpx.get(f"{ANYTHINGLLM_URL}/api/v1/workspace/{slug}", headers=_headers())
    ws_resp.raise_for_status()
    workspace = ws_resp.json().get("workspace", [{}])[0]
    ws_name = workspace.get("name", "未知工作区")
    embedded = {d.get("docpath"): d for d in workspace.get("documents", [])}

    # 获取全局文档库
    docs_resp = httpx.get(f"{ANYTHINGLLM_URL}/api/v1/documents", headers=_headers())
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


@mcp.tool()
def upload_document(file_path: str) -> str:
    """上传本地文件到第一个工作区，并立即触发向量化嵌入。

    file_path: 本地文件的绝对路径（或相对当前目录的路径）。
    """
    path = Path(file_path).expanduser()
    if not path.is_file():
        return f"错误：文件不存在或不支持读取 {path}"

    slug = _get_first_workspace_slug()
    try:
        with path.open("rb") as handle:
            resp = httpx.post(
                f"{ANYTHINGLLM_URL}/api/v1/document/upload",
                headers=_headers(),
                files={"file": (path.name, handle, "application/octet-stream")},
                data={"addToWorkspaces": slug},
                timeout=120,
            )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as error:
        return f"错误：上传失败，HTTP {error.response.status_code}：{error.response.text[:300]}"
    except httpx.RequestError as error:
        return f"错误：无法连接 AnythingLLM（{ANYTHINGLLM_URL}）：{error}"

    if data.get("error"):
        return f"错误：{data['error']}"
    if not data.get("success"):
        return f"错误：上传未成功，返回内容：{data}"

    documents = data.get("documents") or [{}]
    doc = documents[0]
    return (
        f"已上传并加入工作区「{slug}」：{doc.get('title', path.name)} "
        f"| 位置:{doc.get('location', '?')} "
        f"| 字数:{doc.get('wordCount', '?')} "
        f"| 预估token:{doc.get('token_count_estimate', '?')}"
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8001)

