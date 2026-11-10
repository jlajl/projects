from pathlib import Path

from ..context import ContextStore
from .base import Tool


def build_tools(workspace: Path) -> list[Tool]:
    store = ContextStore(workspace)

    def recall(id: str | None = None, text: str = "") -> str:
        return store.recall(id, text)

    return [
        Tool(
            "recallContext",
            (
                "检索之前压缩保存的原始上下文归档。用于查回压缩摘要中缺失的历史细节。"
                "传入 text 关键词在归档中做全文匹配；可选传入 id 限定只检索某个归档编号。"
            ),
            {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": (
                            "可选，指定要检索的归档编号（如 20261022-153000）。"
                            "留空则检索 .agents/context/ 下所有归档。"
                        ),
                    },
                    "text": {
                        "type": "string",
                        "description": "必需，需要查找的关键词或文本内容。",
                    },
                },
                "required": ["text"],
            },
            recall,
        )
    ]