from datetime import datetime
from pathlib import Path

from .base import Tool

NO_PARAMS = {"type": "object", "properties": {}}


def build_tools(workspace: Path) -> list[Tool]:
    return [
        Tool(
            "getDate",
            "获取当前电脑的日期和时间",
            NO_PARAMS,
            lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
        Tool(
            "getCwd",
            "获取当前工作目录",
            NO_PARAMS,
            lambda: str(workspace),
        ),
    ]
