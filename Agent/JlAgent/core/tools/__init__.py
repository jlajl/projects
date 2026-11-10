"""工具集合。

``Tool`` / ``ToolRegistry`` 按需从 ``.base`` 导出，``build_registry`` 内部才导入
各工具模块与 MCP / 技能依赖。这样单独导入某个工具子模块（例如
``core.tools.filesystem``）不会连带拉起 mcp、yaml 等重依赖，
最小环境下的冒烟测试可以直接跑。
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - 仅供类型检查
    from pathlib import Path

    from ..mcp_client import MCPClientManager
    from ..skills import SkillCatalog
    from .base import Tool, ToolRegistry

__all__ = ["Tool", "ToolRegistry", "build_registry"]

_LAZY = {"Tool": ".base", "ToolRegistry": ".base"}


def __getattr__(name: str) -> Any:
    module_name = _LAZY.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(module_name, __name__), name)


def build_registry(
    workspace: "Path",
    baidu_search_api_key: str = "",
    skill_catalog: "SkillCatalog | None" = None,
    mcp_manager: "MCPClientManager | None" = None,
    search_request_timeout: int = 20,
    search_max_results: int = 8,
    search_snippet_limit: int = 300,
    search_answer_limit: int = 1500,
    web_request_timeout: int = 20,
    web_max_content_chars: int = 8000,
    cli_exec_timeout: int = 30,
    cli_max_stream_chars: int = 4000,
) -> "ToolRegistry":
    from . import (
        cli,
        filesystem,
        mcp_tools,
        recall,
        search,
        skill_creator,
        skill_loader,
        system,
        web_fetch,
    )
    from .base import ToolRegistry

    tools = [
        *system.build_tools(workspace),
        *filesystem.build_tools(workspace),
        *recall.build_tools(workspace),
        *search.build_tools(
            baidu_search_api_key,
            search_request_timeout,
            search_max_results,
            search_snippet_limit,
            search_answer_limit,
        ),
        *web_fetch.build_tools(web_request_timeout, web_max_content_chars),
        *cli.build_tools(workspace, cli_exec_timeout, cli_max_stream_chars),
    ]
    if skill_catalog is not None:
        tools.extend(skill_loader.build_tools(skill_catalog))
    tools.extend(skill_creator.build_tools(workspace, skill_catalog))
    if mcp_manager is not None:
        tools.extend(mcp_tools.build_tools(mcp_manager, {tool.name for tool in tools}))
    return ToolRegistry(tools)
