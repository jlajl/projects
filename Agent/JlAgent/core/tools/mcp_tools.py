import re

from ..mcp_client import MCPClientManager, MCPToolInfo
from .base import Tool

MAX_NAME_LENGTH = 64
_INVALID_CHARS = re.compile(r"[^A-Za-z0-9_-]")


def _sanitize(value: str, fallback: str = "tool") -> str:
    cleaned = _INVALID_CHARS.sub("_", value.strip())
    return cleaned[:MAX_NAME_LENGTH] or fallback


def _unique(base: str, used: set[str]) -> str:
    candidate = base[:MAX_NAME_LENGTH]
    if candidate not in used:
        return candidate
    index = 2
    while True:
        suffix = f"__{index}"
        candidate = base[: MAX_NAME_LENGTH - len(suffix)] + suffix
        if candidate not in used:
            return candidate
        index += 1


def _parameters(schema: object) -> dict:
    if isinstance(schema, dict) and schema.get("type") == "object":
        return schema
    if isinstance(schema, dict) and isinstance(schema.get("properties"), dict):
        return {"type": "object", **schema}
    return {"type": "object", "properties": {}}


def _description(info: MCPToolInfo) -> str:
    origin = f"MCP Server '{info.server}' 提供的工具 '{info.name}'"
    return f"[MCP:{info.server}] {info.description}" if info.description else origin


def build_tools(
    manager: MCPClientManager, used_names: set[str] | None = None
) -> list[Tool]:
    """把已发现的 MCP 工具注册到本地工具集合。

    名称冲突时按 ``<server>__<tool>`` 加上服务器前缀，仍冲突则追加序号，
    并把最终暴露名称与原始工具的映射记录到 manager。
    """
    used = set(used_names or ())
    tools: list[Tool] = []

    for info in manager.tools:
        base = _sanitize(info.name)
        if base in used:
            base = f"{_sanitize(info.server, 'server')}__{base}"
        exposed = _unique(base, used)
        used.add(exposed)
        manager.bind(exposed, info)
        tools.append(
            Tool(
                exposed,
                _description(info),
                _parameters(info.input_schema),
                _make_handler(manager, exposed),
            )
        )

    return tools


def _make_handler(manager: MCPClientManager, exposed: str):
    def call(**arguments) -> str:
        return manager.invoke(exposed, arguments)

    return call
