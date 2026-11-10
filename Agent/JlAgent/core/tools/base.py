import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., str]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool] = ()):
        self._tools = {tool.name: tool for tool in tools}

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    def list(self) -> list[Tool]:
        return list(self._tools.values())

    def add(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def add_many(self, tools: Iterable[Tool]) -> None:
        for tool in tools:
            self._tools[tool.name] = tool

    def execute(self, name: str, arguments: str) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"错误：未知工具 {name}"
        try:
            return tool.handler(**json.loads(arguments or "{}"))
        except Exception as error:
            return f"工具执行失败: {error}"
