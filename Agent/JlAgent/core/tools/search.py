import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import Tool

SEARCH_ENDPOINT = "https://qianfan.baidubce.com/v2/ai_search/web_search"


def _short(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else f"{text[:limit]}…"


def _format_results(
    data: dict, max_results: int, snippet_limit: int, answer_limit: int
) -> str:
    code = data.get("code", data.get("error_code"))
    if code not in (None, 0, "0", "success"):
        message = (
            data.get("message")
            or data.get("msg")
            or data.get("error_msg")
            or "未知错误"
        )
        return f"错误：搜索 API 返回错误（{code}）：{message}"

    references = (
        data.get("references")
        or (data.get("search_info") or {}).get("search_results")
        or data.get("search_results")
        or data.get("results")
        or []
    )
    if not isinstance(references, list):
        references = []
    references = [item for item in references if isinstance(item, dict)]

    answer = data.get("answer") or data.get("summary")
    content = data.get("content")
    if not answer and isinstance(content, str):
        answer = content
    if not answer and isinstance(content, list) and content and isinstance(content[0], dict):
        answer = content[0].get("content")

    if not answer and not references:
        return "未找到相关搜索结果"

    lines = []
    if answer:
        lines.extend(["搜索摘要：", _short(str(answer), answer_limit), ""])

    lines.append(f"参考来源（{len(references)} 条）：")
    for index, item in enumerate(references[:max_results], 1):
        title = item.get("title") or "无标题"
        url = item.get("url") or item.get("link") or ""
        lines.append(f"{index}. {title}")
        if url:
            lines.append(f"   {url}")
        snippet = item.get("snippet") or item.get("content") or item.get("abstract")
        if snippet:
            lines.append(f"   摘要：{_short(str(snippet), snippet_limit)}")

    return "\n".join(lines)


def build_tools(
    api_key: str,
    request_timeout: int = 20,
    max_results: int = 8,
    snippet_limit: int = 300,
    answer_limit: int = 1500,
) -> list[Tool]:
    def search_web(query: str) -> str:
        query = query.strip()
        if not query:
            return "错误：搜索关键词不能为空"
        if not api_key:
            return "错误：未配置搜索服务，请在 config.ini 的 [search] 小节设置 baidu_api_key"

        payload = {
            "messages": [{"role": "user", "content": query}],
            "search_source": "baidu_search_v2",
            "resource_type_filter": [{"type": "web", "top_k": max_results}],
        }
        request = Request(
            SEARCH_ENDPOINT,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=request_timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:300]
            return f"错误：搜索 API 返回 HTTP {error.code}，详情：{detail}"
        except (TimeoutError, socket.timeout):
            return f"错误：搜索服务请求超时（{request_timeout} 秒）"
        except URLError as error:
            return f"错误：无法连接搜索服务，{error.reason}"
        except json.JSONDecodeError:
            return "错误：搜索 API 返回了无法解析的响应"

        if not isinstance(data, dict):
            return "错误：搜索 API 返回格式异常"
        return _format_results(data, max_results, snippet_limit, answer_limit)

    return [
        Tool(
            "searchWeb",
            "联网搜索互联网上的最新信息，返回搜索摘要和参考来源。"
            "当用户询问实时新闻、近期事件、当前数据或需要核实的信息时使用。",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或需要检索的问题",
                    }
                },
                "required": ["query"],
            },
            search_web,
        )
    ]
