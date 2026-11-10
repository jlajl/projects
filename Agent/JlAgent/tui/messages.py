from rich.markdown import Markdown
from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Collapsible, Static


def preview(text: str, limit: int = 1200) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n…（共 {len(text)} 字符，已截断）"


def describe_error(error: Exception) -> str:
    message = str(error)
    if "Connection error" in message:
        return (
            f"无法连接模型服务：{message}。"
            "请确认 LM Studio 已启动并开启本地 API Server，且 config.ini 中 base_url 正确。"
        )
    return message


class WelcomeMessage(Static):
    def __init__(self, model: str, workspace: str):
        content = (
            "### 欢迎使用 JlAgent\n\n"
            f"- 模型：`{model}`\n"
            f"- 工作区：`{workspace}`\n\n"
            "直接输入自然语言指令，例如：**列出当前目录并读取 README.md**"
        )
        super().__init__(Markdown(content), classes="welcome")
        self.border_title = "开始"


class UserMessage(Static):
    def __init__(self, content: str):
        super().__init__(Text(content), classes="message user-message")
        self.border_title = "你"


class AssistantMessage(Static):
    def __init__(self, content: str):
        super().__init__(Markdown(content), classes="message assistant-message")
        self.border_title = "JlAgent"


class MarkdownMessage(Static):
    def __init__(self, content: str):
        super().__init__(Markdown(content), classes="message assistant-message")
        self.border_title = "JlAgent"


class SystemMessage(Static):
    def __init__(self, content: str):
        super().__init__(Text(content, style="dim"), classes="system-message")


class ErrorMessage(Static):
    def __init__(self, content: str):
        super().__init__(Text(f"错误：{content}"), classes="message error-message")
        self.border_title = "错误"


class WarningMessage(Static):
    def __init__(self, content: str):
        super().__init__(
            Text(f"⚠ {content}", style="bold yellow"), classes="system-message"
        )


class CapabilityItem(Static):
    def __init__(self, name: str, description: str):
        content = Text()
        content.append(name, style="bold")
        content.append(f"\n{description}", style="dim")
        super().__init__(content, classes="capability-item")


class ToolCallMessage(Static):
    def __init__(self, name: str, arguments: str):
        super().__init__(
            Text(f"⚙ {name}  {preview(arguments, 200)}", style="dim italic"),
            classes="tool-call",
        )


class ToolResultMessage(Collapsible):
    def __init__(self, name: str, result: str):
        super().__init__(
            Static(preview(result), classes="tool-result-content"),
            title=f"↳ {name} 结果 · {len(result)} 字符",
            collapsed=True,
            classes="tool-result",
        )


class ThinkingBlock(Collapsible):
    def __init__(self):
        self._placeholder = Static(
            Text("正在思考…", style="dim italic"), classes="thought-text"
        )
        self.body = Vertical(self._placeholder, classes="thinking-body")
        super().__init__(
            self.body,
            title="思考中…",
            collapsed=False,
            classes="thinking-block",
        )
        self.tool_count = 0
        self._pending = []
        self._has_content = False

    def _add(self, widget) -> None:
        self._pending.append(widget)
        self._has_content = True
        if self.body.is_mounted:
            self._flush()
        else:
            self.call_after_refresh(self._flush)

    def _flush(self) -> None:
        if not self._pending:
            return
        if not self.body.is_mounted:
            self.call_after_refresh(self._flush)
            return
        pending, self._pending = self._pending, []
        if self._placeholder.is_mounted:
            self._placeholder.remove()
        for widget in pending:
            self.body.mount(widget)

    def add_thought(self, content: str, reasoning: bool = False) -> None:
        renderable = Text(content, style="dim italic") if reasoning else Markdown(content)
        self._add(Static(renderable, classes="thought-text"))

    def add_tool_call(self, name: str, arguments: str) -> None:
        self.tool_count += 1
        self.title = f"思考中 · {self.tool_count} 次工具调用"
        self._add(ToolCallMessage(name, arguments))

    def add_tool_result(self, name: str, result: str) -> None:
        self._add(ToolResultMessage(name, result))

    def finish(self) -> None:
        if not self._has_content:
            self._placeholder.update(
                Text("模型未展开推理，也未调用工具，直接作答", style="dim italic")
            )
        self.title = (
            f"思考过程 · {self.tool_count} 次工具调用"
            if self.tool_count
            else "思考过程"
        )
        self.collapsed = True
