import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from .context import DEFAULT_CONTEXT_WINDOW

_INLINE_TOOL_CALL = re.compile(
    r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL
)


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class LLMResponse:
    content: str
    tool_calls: list[ToolCall]
    message: dict[str, Any]
    reasoning: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


def _extract_inline_tool_calls(content: str) -> tuple[str, list[ToolCall]]:
    calls: list[ToolCall] = []

    def replace(match: re.Match[str]) -> str:
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return match.group(0)
        if not isinstance(data, dict):
            return match.group(0)
        name = data.get("name")
        if not isinstance(name, str) or not name:
            return match.group(0)
        arguments = data.get("arguments", {})
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments, ensure_ascii=False)
        calls.append(ToolCall(f"call_{uuid.uuid4().hex}", name, arguments))
        return ""

    cleaned = _INLINE_TOOL_CALL.sub(replace, content)
    if not calls:
        return content, []
    return cleaned.strip(), calls


def _read_reasoning(reply: Any) -> str:
    value = getattr(reply, "reasoning_content", None)
    if not isinstance(value, str) or not value:
        extra = getattr(reply, "model_extra", None)
        if isinstance(extra, dict):
            value = extra.get("reasoning_content") or extra.get("reasoning")
    return value if isinstance(value, str) else ""


class LLMClient:
    def __init__(self, api_key: str, base_url: str, model_name: str):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model_name = model_name

    def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        completion = self._client.chat.completions.create(
            model=self._model_name, messages=messages, tools=tools
        )
        reply = completion.choices[0].message

        usage = getattr(completion, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)

        content = reply.content or ""
        tool_calls = [
            ToolCall(call.id, call.function.name, call.function.arguments or "{}")
            for call in reply.tool_calls or []
        ]
        if not tool_calls:
            content, tool_calls = _extract_inline_tool_calls(content)

        message: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                }
                for call in tool_calls
            ]

        return LLMResponse(
            content,
            tool_calls,
            message,
            _read_reasoning(reply),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    def context_window(self) -> tuple[int, bool]:
        """尽力探测模型的上下文窗口；无法获得时返回 (默认值, False)。"""
        try:
            client = self._client.with_options(timeout=5.0)
            for model in client.models.list():
                if model.id == self._model_name:
                    size = getattr(model, "context_length", None)
                    if isinstance(size, int) and size > 0:
                        return size, True
        except Exception:
            pass
        return DEFAULT_CONTEXT_WINDOW, False
