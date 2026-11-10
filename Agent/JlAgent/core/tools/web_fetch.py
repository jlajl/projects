import subprocess
from urllib.parse import urlparse

import trafilatura

from .base import Tool

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


def _fetch_html(url: str, request_timeout: int) -> tuple[bytes | None, str]:
    command = [
        "curl",
        "-L",
        "-f",
        "-sS",
        "--compressed",
        "--max-time",
        str(request_timeout),
        "--user-agent",
        USER_AGENT,
        url,
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, timeout=request_timeout + 5
        )
    except FileNotFoundError:
        return None, "错误：未找到 curl 程序，请确认系统已安装 curl"
    except subprocess.TimeoutExpired:
        return None, f"错误：网页请求超时（{request_timeout} 秒）"

    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()[:300]
        return (
            None,
            f"错误：网页访问失败（curl 退出码 {completed.returncode}）："
            f"{detail or '无错误详情'}",
        )
    if not completed.stdout:
        return None, "错误：网页返回内容为空"
    return completed.stdout, ""


def _extract_markdown(html: bytes, url: str) -> tuple[str | None, str]:
    try:
        markdown = trafilatura.extract(
            html,
            url=url,
            output_format="markdown",
            include_comments=False,
            include_tables=True,
            include_links=True,
            include_formatting=True,
            include_images=False,
            deduplicate=True,
        )
    except Exception as error:
        return None, f"错误：网页 HTML 解析失败：{error}"
    if not markdown or not markdown.strip():
        return None, "错误：未能从网页中提取正文"
    return markdown.strip(), ""


def _extract_title(html: bytes, url: str) -> str:
    try:
        metadata = trafilatura.extract_metadata(html, default_url=url)
    except Exception:
        return ""
    return (metadata.title or "").strip() if metadata else ""


def _truncate(markdown: str, max_content_chars: int) -> str:
    if len(markdown) <= max_content_chars:
        return markdown
    return (
        f"{markdown[:max_content_chars]}\n\n"
        f"…（正文已截断，共 {len(markdown)} 字符）"
    )


def fetch_web(url: str, request_timeout: int = 20, max_content_chars: int = 8000) -> str:
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "错误：仅支持有效的 http/https 网页地址"

    html, error = _fetch_html(url, request_timeout)
    if error:
        return error

    markdown, error = _extract_markdown(html, url)
    if error:
        return error

    title = _extract_title(html, url)
    if title and title not in markdown[:200]:
        markdown = f"# {title}\n\n{markdown}"

    header = f"网页：{url}"
    if title:
        header += f"\n标题：{title}"
    return f"{header}\n\n{_truncate(markdown, max_content_chars)}"


def build_tools(
    request_timeout: int = 20, max_content_chars: int = 8000
) -> list[Tool]:
    def _fetch(url: str) -> str:
        return fetch_web(url, request_timeout, max_content_chars)

    return [
        Tool(
            "fetchWeb",
            "获取指定网页的正文并转换为 Markdown，保留标题、段落、列表、表格和链接。"
            "当需要阅读搜索结果中的具体网页、获取详细资料或核实信息时使用。",
            {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "网页 URL，必须以 http:// 或 https:// 开头",
                    }
                },
                "required": ["url"],
            },
            _fetch,
        )
    ]
