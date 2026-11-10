"""模态选择屏：恢复历史会话。"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Header, OptionList, Static
from textual.widgets._option_list import Option

from core.session import SessionSummary


class SessionPickerScreen(Screen):
    BINDINGS = [Binding("escape", "cancel", "取消")]

    def __init__(self, sessions: list[SessionSummary]):
        super().__init__()
        self._sessions = sessions

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            Text("选择要恢复的会话（↑↓ 选择，Enter 恢复，Esc 取消）", style="bold"),
            id="picker-title",
        )
        options = [
            Option(self._label(summary), id=summary.id) for summary in self._sessions
        ]
        yield OptionList(*options, id="session-list")

    def _label(self, summary: SessionSummary) -> str:
        title = summary.title or "(无标题)"
        return f"{summary.updated_at}  ·  {title}"

    def on_mount(self) -> None:
        self.query_one("#session-list", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option = event.option
        if option is not None and option.id is not None:
            session_id = str(option.id)
            for summary in self._sessions:
                if summary.id == session_id:
                    self.dismiss(summary)
                    return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)