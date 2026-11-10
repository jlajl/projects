"""JlAgent 核心包。

按需导出：``from core import Agent`` 语义不变，但导入子模块（如
``core.tools.system``）时不再连带拉起 mcp / openai 等重依赖，
使最小环境（例如只跑文件工具的单测）也能导入。
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - 仅供类型检查
    from .agent import Agent
    from .config import Config
    from .llm import LLMClient

__all__ = ["Agent", "Config", "LLMClient"]

_LAZY = {
    "Agent": ".agent",
    "Config": ".config",
    "LLMClient": ".llm",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(module_name, __name__), name)
