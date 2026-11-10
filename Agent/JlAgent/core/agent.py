from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from .tools.base import Tool, ToolRegistry
from .events import (
    AgentError,
    AgentEvent,
    AssistantMessage,
    Thinking,
    ToolCallFinished,
    ToolCallStarted,
)
from .llm import LLMClient
from .mcp_client import MCPClientManager
from .context import (
    DEFAULT_CONTEXT_WINDOW,
    THRESHOLD,
    TARGET_SUMMARY_TOKENS,
    ContextStore,
    build_compact_messages,
    estimate_history_tokens,
    messages_to_text,
    trim_to_tokens,
)


AGENTS_MD_NAME = "agents_md"


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        system_prompt: str = "",
        max_steps: int = 8,
        mcp_manager: MCPClientManager | None = None,
        workspace: Path | None = None,
        context_window: int | None = None,
        context_window_known: bool = False,
    ):
        self._llm = llm
        self._registry = registry
        self._system_prompt = system_prompt
        self._max_steps = max_steps
        self._messages: list[dict] = []
        self.mcp_manager = mcp_manager
        self._context_store = ContextStore(workspace or Path.cwd())
        self._context_window = context_window or DEFAULT_CONTEXT_WINDOW
        self._context_window_known = context_window_known
        self._last_prompt_tokens: int | None = None
        self._input_blocked = False

    def reset(self) -> None:
        self._messages.clear()
        self._last_prompt_tokens = None
        self._input_blocked = False

    @property
    def messages(self) -> list[dict]:
        return list(self._messages)

    def set_messages(self, messages: list[dict]) -> None:
        self._messages = [dict(message) for message in messages]
        self._last_prompt_tokens = None
        self._input_blocked = False

    def add_tools(self, tools: list[Tool]) -> None:
        for tool in tools:
            self._registry.add(tool)

    def inject_agents_md(self, content: str) -> bool:
        """把 AGENTS.md 内容作为一条消息注入，已注入过则返回 False（一次注入）。"""
        if not content or not content.strip():
            return False
        if any(message.get("name") == AGENTS_MD_NAME for message in self._messages):
            return False
        self._messages.insert(
            0,
            {
                "role": "user",
                "content": f"【项目约定 · AGENTS.md】\n\n{content.strip()}",
                "name": AGENTS_MD_NAME,
            },
        )
        self._last_prompt_tokens = None
        return True

    def close(self) -> None:
        if self.mcp_manager is not None:
            self.mcp_manager.close()
            self.mcp_manager = None

    @property
    def tools(self) -> list[Tool]:
        return self._registry.list()

    # ----- 上下文监控与压缩 ------------------------------------------------
    def context_usage_tokens(self) -> int:
        if self._last_prompt_tokens:
            return self._last_prompt_tokens
        return estimate_history_tokens(self._system_prompt, self._messages)

    @property
    def context_window_tokens(self) -> int:
        return self._context_window

    @property
    def context_window_known(self) -> bool:
        return self._context_window_known

    def usage_ratio(self) -> float:
        window = self._context_window or DEFAULT_CONTEXT_WINDOW
        return self.context_usage_tokens() / window

    @property
    def input_blocked(self) -> bool:
        return self._input_blocked

    def should_block_input(self) -> bool:
        return self.usage_ratio() >= THRESHOLD and not self._input_blocked

    def block_input(self) -> None:
        self._input_blocked = True

    def compact(self) -> str:
        """压缩当前会话：归档 → 调用 LLM 摘要 → 替换历史。失败时保留原上下文。"""
        if not self._messages:
            return "当前会话没有需要压缩的上下文"

        history_text = messages_to_text(self._messages)
        now = datetime.now()

        try:
            archive_id = self._context_store.save(self._messages, now=now)
        except OSError as error:
            return f"压缩失败：无法保存原始上下文归档（{error}），已保留原上下文"

        try:
            summary = self._llm.chat(
                build_compact_messages(history_text), tools=[]
            ).content.strip()
        except Exception as error:
            return (
                f"压缩失败：生成摘要时出错（{error}）。"
                f"原始上下文已归档为 {archive_id}，可重新执行 /compact"
            )

        if not summary:
            return (
                f"压缩失败：模型未返回摘要。"
                f"原始上下文已归档为 {archive_id}，可重新执行 /compact"
            )

        summary = trim_to_tokens(summary, TARGET_SUMMARY_TOKENS)
        note = (
            f"此前上下文已于 {now:%Y-%m-%d %H:%M:%S} 完成压缩，"
            f"原始上下文保存在编号为 {archive_id} 的归档文件中。"
            "如需查找历史信息，请使用 recallContext 工具。"
        )
        self._messages = [{"role": "user", "content": f"{summary}\n\n{note}"}]
        self._last_prompt_tokens = None
        self._input_blocked = False
        return f"上下文压缩完成，归档编号 {archive_id}"

    # ----- 工具调用主流程 --------------------------------------------------
    def run(self, prompt: str) -> Iterator[AgentEvent]:
        self._messages.append({"role": "user", "content": prompt})
        for _ in range(self._max_steps):
            response = self._llm.chat(self._history(), self._registry.schemas())
            if response.prompt_tokens:
                self._last_prompt_tokens = response.prompt_tokens
            self._messages.append(response.message)

            if response.reasoning:
                yield Thinking(response.reasoning)

            if not response.tool_calls:
                yield AssistantMessage(
                    response.content or "（模型未返回内容）", final=True
                )
                return

            if response.content:
                yield AssistantMessage(response.content, final=False)

            for call in response.tool_calls:
                yield ToolCallStarted(call.name, call.arguments)
                result = self._registry.execute(call.name, call.arguments)
                yield ToolCallFinished(call.name, result)
                self._messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": result}
                )

        yield AgentError(f"已达到最大工具调用轮数 {self._max_steps}")

    def _history(self) -> list[dict]:
        if not self._system_prompt:
            return self._messages
        return [{"role": "system", "content": self._system_prompt}, *self._messages]
