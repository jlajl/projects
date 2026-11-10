from collections import defaultdict

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, OptionList, Static
from textual.widgets._option_list import Option

from core import events
from core.agent import AGENTS_MD_NAME
from core.bootstrap import bind_mcp_tools, create_agent, inject_agents_md
from core.config import Config, default_config_path
from core.context import THRESHOLD
from core.session import SessionStore, SessionSummary
from core.skills import SkillCatalog
from .messages import (
    AssistantMessage,
    CapabilityItem,
    ErrorMessage,
    MarkdownMessage,
    SystemMessage,
    ThinkingBlock,
    UserMessage,
    WarningMessage,
    WelcomeMessage,
    describe_error,
)
from .screens import SessionPickerScreen


class JlAgentApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "JlAgent"
    SUB_TITLE = "本地文件管理助手"
    BINDINGS = [
        Binding("ctrl+q", "quit", "退出"),
        Binding("ctrl+l", "clear_screen", "清屏"),
        Binding("ctrl+n", "new_session", "新会话"),
        Binding("down", "slash_down", show=False),
        Binding("up", "slash_up", show=False),
        Binding("escape", "slash_cancel", show=False),
    ]

    def __init__(
        self,
        config: Config,
        skill_catalog: SkillCatalog | None = None,
        config_created: bool = False,
    ):
        super().__init__()
        self.config = config
        self.catalog = (
            skill_catalog
            if skill_catalog is not None
            else SkillCatalog.discover(config.workspace, config.skills_dir)
        )
        self.agent = create_agent(config, self.catalog)
        self._session_store = SessionStore(config.workspace)
        self._session_id: str | None = None
        self._config_created = config_created
        self.busy = False
        self._thinking: ThinkingBlock | None = None
        self._panel_collapsed = False

        self.SLASH_COMMANDS = [
            ("new", "新建会话并自动保存当前历史"),
            ("resume", "恢复历史会话"),
            ("save", "保存当前会话"),
            ("compact", "压缩上下文"),
            ("clear", "清空屏幕显示"),
            ("help", "显示帮助"),
            ("status", "显示状态"),
            ("quit", "退出"),
        ]
        self._slash_handlers = {
            "new": self._cmd_new,
            "resume": self._cmd_resume,
            "save": self._cmd_save,
            "compact": self._cmd_compact,
            "clear": self._cmd_clear,
            "help": self._cmd_help,
            "status": self._cmd_status,
            "quit": self._cmd_quit,
        }

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            with Vertical(id="chat"):
                yield VerticalScroll(id="conversation")
                with Horizontal(id="statusbar"):
                    yield Static("就绪", id="state")
                    yield Static("上下文 --/--", id="context")
                    yield Static(
                        f"{self.config.model_name} · {self.config.workspace}",
                        id="info",
                    )
                yield OptionList(id="slash-options", classes="slash-panel")
                yield Input(placeholder="输入指令，Enter 发送；输入 / 弹出命令面板", id="prompt")
            with Vertical(id="capabilities"):
                yield Button("收起功能与技能", id="panel-toggle")
                yield VerticalScroll(id="capability-content")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#prompt", Input).border_title = "指令"
        self._welcome()
        self._refresh_sidebar()
        self._update_context_display()
        self._set_busy(False)
        if self._config_created:
            path = default_config_path()
            self._mount(
                WarningMessage(
                    f"已在当前目录生成 {path}（含占位信息）。"
                    "请修改 [llm] 中的模型地址与密钥，保存后重新启动才能正常工作。"
                )
            )
            self.notify(
                "已生成 config.ini，请填写模型信息后重新启动",
                severity="warning",
                timeout=10,
            )
        self._start_mcp_async()

    def on_unmount(self) -> None:
        self.agent.close()

    # ----- 边栏渲染 ------------------------------------------------------
    def _refresh_sidebar(self) -> None:
        content = self.query_one("#capability-content", VerticalScroll)
        content.remove_children()
        content.mount(*list(self._sidebar_items()))

    def _sidebar_items(self):
        tools = self.agent.tools
        yield Static(Text(f"功能 · {len(tools)}", style="bold"), classes="panel-title")
        for tool in tools:
            yield CapabilityItem(tool.name, tool.description)

        skills = self.catalog.skills
        yield Static(Text(f"技能 · {len(skills)}", style="bold"), classes="panel-title")
        if not skills:
            yield Static(
                Text("未发现 Skill（.agents/skills）", style="dim"),
                classes="capability-empty",
            )
        else:
            for skill in skills:
                yield CapabilityItem(skill.name, skill.description)

        yield from self._mcp_sidebar_items()

    def _mcp_sidebar_items(self):
        manager = self.agent.mcp_manager
        yield Static(Text("MCP 服务器", style="bold"), classes="panel-title")
        if manager is None:
            yield Static(
                Text("未发现 .mcp.json", style="dim"), classes="capability-empty"
            )
            return

        names = manager.server_names
        if not names:
            yield Static(Text("未配置 Server", style="dim"), classes="capability-empty")
            return

        connected = set(manager.connected_servers)
        by_server: dict[str, list[str]] = defaultdict(list)
        for info in manager.tools:
            by_server[info.server].append(info.name)

        for name in names:
            tool_names = by_server.get(name, [])
            if name in connected:
                status = f"已连接 · {len(tool_names)} 个工具"
            else:
                error = next(
                    (
                        line
                        for line in manager.errors
                        if line.startswith(f"MCP Server '{name}'")
                    ),
                    "",
                )
                status = error or "连接中…"
            yield CapabilityItem(name, status)
            for tool_name in tool_names:
                yield Static(
                    Text(f"    · {tool_name}", style="dim"),
                    classes="capability-empty",
                )

    def _start_mcp_async(self) -> None:
        manager = self.agent.mcp_manager
        if manager is None:
            return
        self._mount(SystemMessage("正在后台连接 MCP Server…"))
        manager.start_async(on_update=self._on_mcp_update)

    def _on_mcp_update(self) -> None:
        # 运行在 MCP 后台线程，调度回 UI 线程刷新
        self.call_from_thread(self._refresh_mcp)

    def _refresh_mcp(self) -> None:
        bind_mcp_tools(self.agent)
        self._refresh_sidebar()
        self._update_context_display()

    # ----- 上下文展示 ----------------------------------------------------
    def _fmt_k(self, tokens: int) -> str:
        if tokens >= 1000:
            return f"{tokens / 1000:.1f}k"
        return str(tokens)

    def _fmt_window(self, tokens: int) -> str:
        if tokens >= 1000 and tokens % 1000 == 0:
            return f"{tokens // 1000}k"
        return self._fmt_k(tokens)

    def _update_context_display(self) -> None:
        agent = self.agent
        used = agent.context_usage_tokens()
        window = agent.context_window_tokens
        ratio = agent.usage_ratio()
        suffix = "" if agent.context_window_known else "（默认）"
        label = (
            f"上下文 {self._fmt_k(used)} / {self._fmt_window(window)}"
            f" · {ratio * 100:.1f}%{suffix}"
        )
        if ratio >= THRESHOLD:
            style = "bold red"
        elif ratio >= 0.6:
            style = "bold yellow"
        else:
            style = "bold"
        self.query_one("#context", Static).update(Text(label, style=style))

    # ----- 输入 ----------------------------------------------------------
    def on_input_changed(self, event: Input.Changed) -> None:
        if self.busy:
            self._hide_slash_panel()
            return
        value = event.value
        if value.startswith("/") and " " not in value:
            self._update_slash_panel(value)
        else:
            self._hide_slash_panel()

    def _update_slash_panel(self, value: str) -> None:
        prefix = value[1:].strip().lower()
        matches = [
            (name, desc)
            for name, desc in self.SLASH_COMMANDS
            if name.startswith(prefix)
        ]
        panel = self.query_one("#slash-options", OptionList)
        if not matches:
            self._hide_slash_panel()
            return
        panel.clear_options()
        panel.add_options([Option(f"/{name} — {desc}", id=name) for name, desc in matches])
        panel.highlighted = 0
        panel.set_class(True, "visible")

    def _hide_slash_panel(self) -> None:
        panel = self.query_one("#slash-options", OptionList)
        panel.set_class(False, "visible")
        panel.clear_options()

    def _slash_visible(self) -> bool:
        return self.query_one("#slash-options", OptionList).has_class("visible")

    def _highlighted_command(self) -> str | None:
        panel = self.query_one("#slash-options", OptionList)
        if not panel.has_class("visible"):
            return None
        option = panel.highlighted_option
        if option is not None and option.id is not None:
            return str(option.id)
        return None

    def action_slash_down(self) -> None:
        if self._slash_visible():
            self.query_one("#slash-options", OptionList).action_cursor_down()

    def action_slash_up(self) -> None:
        if self._slash_visible():
            self.query_one("#slash-options", OptionList).action_cursor_up()

    def action_slash_cancel(self) -> None:
        self._hide_slash_panel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        prompt = event.value.strip()
        if not prompt or self.busy:
            event.input.value = ""
            return
        if prompt.startswith("/"):
            event.input.value = ""
            self._handle_slash_command(prompt)
            return
        if self.agent.input_blocked:
            event.input.value = ""
            self.notify(
                "上下文已达到阈值，请先执行 /compact", severity="warning"
            )
            self._mount(
                WarningMessage(
                    "上下文已达 80% 阈值，普通输入已暂停。请输入 /compact 压缩上下文后继续。"
                )
            )
            return
        event.input.value = ""
        self._thinking = None
        self._mount(UserMessage(prompt))
        self._thinking_block()
        self._set_busy(True)
        self._run_agent(prompt)

    def _handle_slash_command(self, prompt: str) -> None:
        word = prompt[1:].strip().split()[0].lower() if prompt[1:].strip() else ""
        selected = self._highlighted_command()
        self._hide_slash_panel()
        if word in self._slash_handlers:
            name = word
        elif selected is not None:
            name = selected
        else:
            self._mount(
                ErrorMessage(
                    f"未知命令 /{word or prompt[1:].strip()}，输入 /help 查看可用命令"
                )
            )
            return
        self._slash_handlers[name]()

    # ----- 斜杠命令实现 --------------------------------------------------
    def _cmd_quit(self) -> None:
        self.exit()

    def _cmd_new(self) -> None:
        if self.busy:
            self.notify("当前任务执行中，请稍后再试", severity="warning")
            return
        self._save_current_session()
        self.agent.reset()
        inject_agents_md(self.agent, self.config.workspace)
        self._session_id = self._session_store.new_id()
        self._thinking = None
        self.query_one("#conversation", VerticalScroll).remove_children()
        self._welcome()
        self._update_context_display()
        self._set_busy(False)

    def _cmd_save(self) -> None:
        summary = self._save_current_session()
        if summary is None:
            self._mount(SystemMessage("当前会话为空，无需保存"))
        else:
            self._mount(
                SystemMessage(f"已保存会话 {summary.id}（{summary.title}）")
            )

    def _cmd_resume(self) -> None:
        if self.busy:
            self.notify("当前任务执行中，请稍后再试", severity="warning")
            return
        summaries = self._session_store.list_sessions()
        if not summaries:
            self._mount(SystemMessage("没有可恢复的历史会话"))
            return
        self.push_screen(SessionPickerScreen(summaries), self._on_resume_picked)

    def _cmd_compact(self) -> None:
        self._start_compact()

    def _cmd_clear(self) -> None:
        self.action_clear_screen()

    def _cmd_help(self) -> None:
        lines = ["### 可用命令", ""]
        for name, desc in self.SLASH_COMMANDS:
            lines.append(f"- `/{name}`：{desc}")
        lines.append("")
        lines.append("输入 `/` 弹出命令补全面板，用 ↑↓ 选择、Enter 执行、Esc 取消。")
        self._mount(MarkdownMessage("\n".join(lines)))

    def _cmd_status(self) -> None:
        agent = self.agent
        used = agent.context_usage_tokens()
        window = agent.context_window_tokens
        ratio = agent.usage_ratio() * 100
        suffix = "" if agent.context_window_known else "（默认）"
        manager = agent.mcp_manager
        if manager is None:
            mcp = "未配置"
        else:
            mcp = (
                f"已连接 {len(manager.connected_servers)} 个 Server，"
                f"注册 {len(manager.bound_tools)} 个工具"
            )
        session_id = self._session_id or "（未保存）"
        self._mount(
            MarkdownMessage(
                f"- 会话：`{session_id}`\n"
                f"- 上下文：{self._fmt_k(used)} / {self._fmt_window(window)}"
                f"（{ratio:.1f}%{suffix}）\n"
                f"- MCP：{mcp}"
            )
        )

    # ----- 会话保存与恢复 -------------------------------------------------
    def _save_current_session(self) -> SessionSummary | None:
        messages = self.agent.messages
        if not self._has_real_content(messages):
            return None
        if self._session_id is None:
            self._session_id = self._session_store.new_id()
        return self._session_store.save(self._session_id, messages)

    def _has_real_content(self, messages: list[dict]) -> bool:
        return any(
            message.get("role") == "user"
            and message.get("name") != AGENTS_MD_NAME
            and isinstance(message.get("content"), str)
            and message.get("content").strip()
            for message in messages
        )

    def _on_resume_picked(self, summary: SessionSummary | None) -> None:
        if summary is None:
            return
        try:
            messages = self._session_store.load(summary.id)
        except (FileNotFoundError, OSError, ValueError) as error:
            self._mount(ErrorMessage(f"恢复会话失败：{error}"))
            return
        self.agent.set_messages(messages)
        inject_agents_md(self.agent, self.config.workspace)
        self._session_id = summary.id
        self._thinking = None
        self.query_one("#conversation", VerticalScroll).remove_children()
        self._render_conversation(messages)
        self._mount(SystemMessage(f"已恢复会话 {summary.id}：{summary.title}"))
        self._update_context_display()
        self._set_busy(False)

    def _render_conversation(self, messages: list[dict]) -> None:
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if role == "user" and message.get("name") == AGENTS_MD_NAME:
                self._mount(SystemMessage("已加载项目 AGENTS.md 约定"))
            elif role == "user" and isinstance(content, str) and content.strip():
                self._mount(UserMessage(content))
            elif role == "assistant" and isinstance(content, str) and content.strip():
                self._mount(AssistantMessage(content))

    # ----- 压缩 ----------------------------------------------------------
    def _start_compact(self) -> None:
        self._mount(SystemMessage("开始压缩上下文…"))
        self._set_busy(True)
        self._run_compact()

    @work(thread=True, exclusive=True)
    def _run_compact(self) -> None:
        try:
            message = self.agent.compact()
        except Exception as error:
            message = f"压缩失败：{describe_error(error)}"
        self.call_from_thread(self._finish_compact, message)

    def _finish_compact(self, message: str) -> None:
        self._finish_thinking()
        self._set_busy(False)
        self._mount(SystemMessage(message))
        self._update_context_display()

    # ----- 面板折叠 ------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "panel-toggle":
            self._set_panel_collapsed(not self._panel_collapsed)

    def _set_panel_collapsed(self, collapsed: bool) -> None:
        self._panel_collapsed = collapsed
        panel = self.query_one("#capabilities", Vertical)
        panel.set_class(collapsed, "collapsed")
        button = self.query_one("#panel-toggle", Button)
        button.label = "«" if collapsed else "收起功能与技能"

    # ----- Agent 主流程 --------------------------------------------------
    @work(thread=True, exclusive=True)
    def _run_agent(self, prompt: str) -> None:
        try:
            for event in self.agent.run(prompt):
                self.call_from_thread(self._handle_event, event)
        except Exception as error:
            self.call_from_thread(
                self._handle_event, events.AgentError(describe_error(error))
            )
        finally:
            self.call_from_thread(self._finish_turn)

    def _handle_event(self, event: events.AgentEvent) -> None:
        if isinstance(event, events.Thinking):
            self._thinking_block().add_thought(event.content, reasoning=True)
        elif isinstance(event, events.AssistantMessage):
            if event.final:
                self._finish_thinking()
                self._mount(AssistantMessage(event.content))
            else:
                self._thinking_block().add_thought(event.content)
        elif isinstance(event, events.ToolCallStarted):
            self._thinking_block().add_tool_call(event.name, event.arguments)
        elif isinstance(event, events.ToolCallFinished):
            self._thinking_block().add_tool_result(event.name, event.result)
        else:
            self._finish_thinking()
            self._mount(ErrorMessage(event.message))
        self._scroll_end()

    def _thinking_block(self) -> ThinkingBlock:
        if self._thinking is None:
            self._thinking = ThinkingBlock()
            self._mount(self._thinking)
        return self._thinking

    def _finish_thinking(self) -> None:
        if self._thinking is not None:
            self._thinking.finish()
            self._thinking = None

    def _finish_turn(self) -> None:
        self._finish_thinking()
        self._update_context_display()
        if self.agent.should_block_input():
            self.agent.block_input()
            self._mount(
                WarningMessage(
                    "上下文使用量已达 80% 阈值，普通输入将被暂停。请输入 /compact 压缩上下文。"
                )
            )
        self._set_busy(False)

    # ----- 基础工具 ------------------------------------------------------
    def _mount(self, widget) -> None:
        self.query_one("#conversation", VerticalScroll).mount(widget)
        self._scroll_end()

    def _scroll_end(self) -> None:
        conversation = self.query_one("#conversation", VerticalScroll)
        self.call_after_refresh(conversation.scroll_end, animate=False)

    def _welcome(self) -> None:
        self._mount(WelcomeMessage(self.config.model_name, str(self.config.workspace)))

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        prompt = self.query_one("#prompt", Input)
        prompt.disabled = busy
        state = self.query_one("#state", Static)
        if busy:
            state.update(Text("运行中", style="bold yellow"))
        elif self.agent.input_blocked:
            state.update(Text("已满 · /compact", style="bold red"))
        else:
            state.update(Text("就绪", style="bold green"))
        if not busy:
            prompt.focus()

    def action_clear_screen(self) -> None:
        if self.busy:
            self.notify("当前任务执行中，请稍后再试", severity="warning")
            return
        self._thinking = None
        self.query_one("#conversation", VerticalScroll).remove_children()
        self._mount(SystemMessage("显示已清空，上下文保留"))

    def action_new_session(self) -> None:
        self._cmd_new()