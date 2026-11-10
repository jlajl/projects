"""上下文压缩、归档与 Token 估算。

实现三项职责：
1. 无需第三方库的简单 Token 估算（CJK 字符按 1 token，其余按约 4 字符 1 token）。
2. 将原始上下文完整归档到 ``.agents/context/<编号>.jsonl``。
3. 提供上下文压缩所用的 LLM Prompt 与摘要裁剪。

不使用向量数据库、Embedding 等复杂框架，检索依赖 Python 原生全文关键词匹配
（见 core/tools/recall.py）。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

DEFAULT_CONTEXT_WINDOW = 128_000
TARGET_SUMMARY_TOKENS = 5_000
THRESHOLD = 0.8
ARCHIVE_SUFFIX = ".jsonl"


# --------------------------------------------------------------------------
# Token 估算
# --------------------------------------------------------------------------
def _is_cjk(char: str) -> bool:
    code = ord(char)
    return (
        0x3400 <= code <= 0x4DBF      # CJK 扩展 A
        or 0x4E00 <= code <= 0x9FFF   # CJK 统一汉字
        or 0xF900 <= code <= 0xFAFF   # CJK 兼容汉字
        or 0x3000 <= code <= 0x303F   # CJK 标点
        or 0xFF00 <= code <= 0xFFEF   # 全角字符
    )


def estimate_tokens(text: str) -> int:
    """估算一段文本的 Token 数。"""
    if not text:
        return 0
    cjk = sum(1 for char in text if _is_cjk(char))
    other = len(text) - cjk
    return cjk + (other + 3) // 4


def estimate_history_tokens(system_prompt: str, messages: list[dict]) -> int:
    """估算 System Prompt + 对话历史 + 工具调用消息的总 Token 数。"""
    total = estimate_tokens(system_prompt)
    for message in messages:
        content = message.get("content")
        total += estimate_tokens(content if isinstance(content, str) else "")
        for call in message.get("tool_calls") or []:
            function = call.get("function", {})
            total += estimate_tokens(
                f"{function.get('name', '')} {function.get('arguments', '')}"
            )
    return total


def trim_to_tokens(text: str, target: int = TARGET_SUMMARY_TOKENS) -> str:
    """当摘要超过目标 Token 数时按比例裁剪，保留首尾重要内容。"""
    if estimate_tokens(text) <= target:
        return text
    ratio = target / estimate_tokens(text)
    keep = max(200, int(len(text) * ratio))
    head_size = keep * 3 // 4
    head = text[:head_size]
    tail = text[-(keep - head_size):] if keep - head_size > 0 else ""
    return head + "\n\n…（摘要过长，已截断）…\n\n" + tail


# --------------------------------------------------------------------------
# 上下文压缩 Prompt
# --------------------------------------------------------------------------
COMPACT_PROMPT = """你是一名 AI Agent 的上下文管理助手。当前会话即将达到上下文窗口限制，需要将历史对话压缩为一份高质量的工作摘要，以便 Agent 在新的上下文中继续执行任务。

请认真阅读提供的历史上下文，提取对后续工作仍然有价值的信息，并生成一份约 5,000 Tokens 的 Markdown 摘要。

摘要应重点保留以下内容：

1. **用户目标与要求**：用户希望完成什么任务？有哪些必须遵守的约束、偏好和验收条件？
2. **已经完成的工作**：哪些任务已经完成？实现了哪些功能？获得了哪些已经验证的结果？
3. **当前工作状态**：Agent 正在处理什么任务？当前进展到哪一步？是否存在尚未解决的问题？
4. **关键技术信息**：保留重要的文件路径、函数名称、接口定义、配置项、执行命令、错误信息和必要的代码片段。
5. **关键决策与原因**：记录用户和 Agent 已经确定的技术方案，以及重要的设计取舍。
6. **下一步任务**：明确接下来应该执行的操作，以及需要继续验证的事项。

请遵守以下要求：

- 优先保留对后续任务有直接影响的信息，删除寒暄、重复讨论、过时的尝试和无关内容。
- 对已经验证的事实与尚未验证的推测作出明确区分。
- 不要将计划完成的任务描述为已经完成。
- 重要的文件路径、函数名称、配置名称和命令应保留准确原文。
- 对失败的尝试，只保留有助于避免重复错误的信息。
- 如果信息存在冲突，应优先保留用户最新确认的要求，并简要说明仍然存在的冲突。
- 如果某些历史细节无法在摘要中完整保留，可简要说明它们已保存到原始上下文归档中，后续可以通过 recallContext 工具重新检索。
- 使用清晰的 Markdown 结构输出摘要，不要附加解释或无关内容。

最终目标：使一个从未阅读过原始对话的 Agent，仅凭这份摘要，就能够理解当前任务、继承关键决策，并继续开展工作。"""


def build_compact_messages(history_text: str) -> list[dict]:
    """构造用于生成上下文摘要的请求消息（不提供任何工具）。"""
    return [
        {"role": "system", "content": COMPACT_PROMPT},
        {"role": "user", "content": f"以下是需要压缩的历史上下文：\n\n{history_text}"},
    ]


def messages_to_text(messages: list[dict]) -> str:
    """把消息列表还原成可读的文本，供压缩 Prompt 使用。"""
    blocks: list[str] = []
    for index, message in enumerate(messages, 1):
        role = message.get("role", "")
        content = message.get("content")
        lines = [f"[{index}] role={role}"]
        if isinstance(content, str) and content.strip():
            lines.append(content.strip())
        for call in message.get("tool_calls") or []:
            function = call.get("function", {})
            lines.append(
                f"tool_call({function.get('name', '')}) -> {function.get('arguments', '')}"
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


# --------------------------------------------------------------------------
# 原始上下文归档
# --------------------------------------------------------------------------
class ContextStore:
    """负责把原始消息归档到 ``.agents/context/`` 并提供全文本检索。"""

    def __init__(self, workspace: Path):
        self.dir = workspace / ".agents" / "context"

    def archive_id(self, now: datetime | None = None) -> str:
        now = now or datetime.now()
        return now.strftime("%Y%m%d-%H%M%S")

    def save(self, messages: list[dict], now: datetime | None = None) -> str:
        """将消息列表完整写入归档，返回归档编号。

        归档必须成功写入后才返回；抛出异常时由调用方决定是否继续压缩。
        """
        self.dir.mkdir(parents=True, exist_ok=True)
        now = now or datetime.now()
        archive_id = self.archive_id(now)
        unique_id = archive_id
        counter = 1
        while (self.dir / f"{unique_id}{ARCHIVE_SUFFIX}").exists():
            unique_id = f"{archive_id}-{counter}"
            counter += 1
        path = self.dir / f"{unique_id}{ARCHIVE_SUFFIX}"
        with path.open("w", encoding="utf-8") as file:
            for message in messages:
                file.write(json.dumps(message, ensure_ascii=False) + "\n")
        return unique_id

    def archives(self) -> list[Path]:
        if not self.dir.is_dir():
            return []
        return sorted(self.dir.glob(f"*{ARCHIVE_SUFFIX}"))

    def recall(self, archive_id: str | None, text: str) -> str:
        """全文关键词检索归档，返回相关片段与来源位置。"""
        if not isinstance(text, str) or not text.strip():
            return "错误：recallContext 的 text 参数不能为空"

        needle = text.strip().lower()
        targets = self._resolve(archive_id)
        if isinstance(targets, str):
            return targets
        if not targets:
            return "错误：未找到任何历史上下文归档"

        matches: list[tuple[str, int, str, str]] = []
        for path in targets:
            aid = path.stem
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for position, raw in enumerate(lines, 1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                preview = _preview(message)
                if needle in preview.lower():
                    snippet = _snippet(preview, needle)
                    matches.append((aid, position, str(message.get("role", "")), snippet))

        if not matches:
            scope = f"归档 {archive_id} 中" if archive_id else "所有归档中"
            return f"未在{scope}找到与「{text}」匹配的内容"

        # 较新归档在前，同一归档内按消息顺序
        matches.sort(key=lambda item: (item[0], item[1]), reverse=True)
        matches = matches[:8]

        lines: list[str] = []
        output = 0
        for aid, position, role, snippet in matches:
            line = f"[归档 {aid} · 第 {position} 条 · 角色 {role}]\n{snippet}"
            if output > 0:
                line = "\n\n" + line
            lines.append(line)
            output += len(line)
            if output >= 6000:
                break
        result = "\n".join(lines)
        if len(matches) > 8 or output >= 6000:
            result += "\n\n…（匹配较多，已截断）"
        return result

    def _resolve(self, archive_id: str | None) -> list[Path] | str:
        if not archive_id:
            return self.archives()
        path = self.dir / f"{archive_id}{ARCHIVE_SUFFIX}"
        if not path.is_file():
            return f"错误：归档 {archive_id} 不存在"
        return [path]


def _preview(message: dict) -> str:
    role = message.get("role", "")
    parts = [message.get("content") if isinstance(message.get("content"), str) else ""]
    for call in message.get("tool_calls") or []:
        function = call.get("function", {})
        parts.append(f"[工具调用] {function.get('name', '')} {function.get('arguments', '')}")
    text = " ".join(part for part in parts if part).strip()
    return f"{role}: {text}" if text else role


def _snippet(text: str, needle: str, radius: int = 180) -> str:
    low = text.lower()
    pos = low.find(needle)
    if pos < 0:
        pos = 0
    start = max(0, pos - radius // 2)
    end = min(len(text), start + radius)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end] + suffix