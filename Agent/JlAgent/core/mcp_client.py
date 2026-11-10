"""MCP（Model Context Protocol）客户端。

负责读取项目目录下的 ``.mcp.json``，通过 MCP Python SDK 连接 stdio 或
Streamable HTTP 的 MCP Server，发现其工具并按需转发调用。

设计要点：
- MCP SDK 是异步接口，而 JlAgent 的工具处理函数是同步的。这里用一个常驻
  后台线程 + 独立事件循环承载所有 MCP 会话，同步调用方通过
  ``asyncio.run_coroutine_threadsafe`` 转发请求。
- 每个 Server 的会话在其协程内保持打开（连接上下文常驻），直到 ``close()``。
- 单个 Server 的连接/初始化失败只记录错误，不影响其他 Server 与本地工具。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import sys
import tempfile
import threading
from collections.abc import Callable, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

CONFIG_FILENAME = ".mcp.json"
DEFAULT_TIMEOUT = 30.0

_HTTP_TRANSPORTS = {
    "http",
    "streamable-http",
    "streamable_http",
    "streamablehttp",
    "remote",
}


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    transport: str  # "stdio" | "http"
    command: str = ""
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    cwd: str = ""
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MCPToolInfo:
    """MCP Server 暴露的一个工具（尚未确定对 LLM 暴露的名称）。"""

    server: str
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class _ServerState:
    session: Any = None
    tools: list[Any] = field(default_factory=list)
    error: str = ""


def find_config_file(*starts: Path) -> Path | None:
    """从给定目录向上逐级查找 ``.mcp.json``。"""
    for start in starts:
        current = Path(start).resolve()
        while True:
            candidate = current / CONFIG_FILENAME
            if candidate.is_file():
                return candidate
            if current.parent == current:
                break
            current = current.parent
    return None


def load_servers(path: Path) -> tuple[list[MCPServerConfig], list[str]]:
    """解析 ``.mcp.json``，返回 Server 配置与逐条错误信息。"""
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError as error:
        return [], [f"MCP 配置读取失败（{path}）：{error}"]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        return [], [
            f"MCP 配置 {path} 不是合法 JSON：第 {error.lineno} 行 {error.msg}"
        ]

    entries = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(entries, dict):
        return [], [f"MCP 配置 {path} 缺少 mcpServers 对象"]

    servers: list[MCPServerConfig] = []
    errors: list[str] = []
    for name, entry in entries.items():
        config, error = _parse_server(str(name), entry)
        if error:
            errors.append(f"MCP Server '{name}' 配置无效：{error}")
        elif config is not None:
            servers.append(config)
    return servers, errors


def _parse_server(name: str, entry: Any) -> tuple[MCPServerConfig | None, str]:
    if not isinstance(entry, dict):
        return None, "配置项必须是 JSON 对象"

    transport = entry.get("type") or entry.get("transport") or ""
    transport = transport.strip().lower() if isinstance(transport, str) else ""
    if not transport:
        transport = "http" if isinstance(entry.get("url"), str) else "stdio"

    if transport in _HTTP_TRANSPORTS:
        url = entry.get("url")
        if not isinstance(url, str) or not url.strip():
            return None, "Streamable HTTP 传输需要提供 url"
        headers = _string_dict(entry.get("headers"), "headers")
        if isinstance(headers, str):
            return None, headers
        return (
            MCPServerConfig(
                name=name, transport="http", url=url.strip(), headers=headers
            ),
            "",
        )

    if transport == "stdio":
        command = entry.get("command")
        if not isinstance(command, str) or not command.strip():
            return None, "stdio 传输需要提供 command"
        args = entry.get("args") or []
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            return None, "args 必须是字符串数组"
        env = _string_dict(entry.get("env"), "env")
        if isinstance(env, str):
            return None, env
        cwd = entry.get("cwd") or ""
        if not isinstance(cwd, str):
            return None, "cwd 必须是字符串"
        return (
            MCPServerConfig(
                name=name,
                transport="stdio",
                command=command.strip(),
                args=tuple(args),
                env=env,
                cwd=cwd,
            ),
            "",
        )

    return None, f"不支持的传输类型 '{transport}'（仅支持 stdio 与 streamable HTTP）"


def _string_dict(value: Any, field_name: str) -> dict[str, str] | str:
    if value is None:
        return {}
    if not isinstance(value, dict):
        return f"{field_name} 必须是 JSON 对象"
    return {str(key): str(item) for key, item in value.items()}


def _open_errlog(transport: str) -> Any:
    """stdio 子进程的 stderr 需要一个带 fileno 的文本流，故用临时文件收集。"""
    if transport != "stdio":
        return None
    try:
        return tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
    except OSError:
        return None


def _read_tail(errlog: Any) -> str:
    if errlog is None:
        return ""
    try:
        errlog.seek(0)
        data = errlog.read()
    except (OSError, ValueError):
        return ""
    return data.strip()[-300:]


def _close(errlog: Any) -> None:
    if errlog is None:
        return
    try:
        errlog.close()
    except OSError:
        pass


def _describe_error(error: BaseException) -> str:
    """把 anyio 的 ExceptionGroup 拆解成可读的单行错误。"""
    inner = getattr(error, "exceptions", None)
    if inner:
        return _describe_error(inner[0])
    message = str(error).strip()
    kind = type(error).__name__
    if isinstance(error, FileNotFoundError):
        return f"找不到可执行文件。{message}" if message else "找不到可执行文件"
    return f"{kind}: {message}" if message else kind


def _format_result(result: Any) -> str:
    """将 MCP ``CallToolResult`` 转换为给 LLM 的文本。"""
    parts: list[str] = []
    for item in getattr(result, "content", None) or []:
        kind = getattr(item, "type", "")
        if kind == "text":
            parts.append(item.text)
        elif kind == "image":
            parts.append(f"[图片内容 {getattr(item, 'mime_type', '')}]")
        elif kind == "audio":
            parts.append(f"[音频内容 {getattr(item, 'mime_type', '')}]")
        elif kind == "resource_link":
            title = getattr(item, "name", "") or getattr(item, "uri", "")
            parts.append(f"[资源链接 {title}]")
        elif kind == "resource":
            resource = getattr(item, "resource", None)
            text = getattr(resource, "text", None)
            if isinstance(text, str) and text:
                parts.append(text)
            else:
                parts.append(f"[嵌入资源 {getattr(resource, 'uri', '')}]")
        else:
            parts.append(str(item))

    text = "\n".join(part for part in parts if part).strip()

    structured = getattr(result, "structured_content", None)
    if structured is not None and not (
        isinstance(structured, dict)
        and len(structured) == 1
        and structured.get("result") == text
    ):
        try:
            dumped = json.dumps(structured, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            dumped = str(structured)
        text = f"{text}\n\n结构化数据：\n{dumped}" if text else f"结构化数据：\n{dumped}"

    if not text:
        text = "（MCP 工具未返回内容）"
    if getattr(result, "is_error", False):
        return f"错误：MCP 工具返回错误\n{text}"
    return text


class MCPClientManager:
    """同步门面：对外提供已发现工具与同步调用能力。"""

    def __init__(
        self,
        servers: Iterable[MCPServerConfig] = (),
        timeout: float = DEFAULT_TIMEOUT,
        config_path: Path | None = None,
    ):
        self._servers = list(servers)
        self._timeout = timeout
        self.config_path = config_path
        self.errors: list[str] = []
        self.tools: list[MCPToolInfo] = []
        self._tool_map: dict[str, MCPToolInfo] = {}
        self._sessions: dict[str, Any] = {}
        self._stop = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._bind_thread: threading.Thread | None = None
        self._started = False

    # ---- 生命周期 -------------------------------------------------------
    def start(self) -> list[str]:
        """启动后台事件循环并逐一连接 Server；失败只记录到 ``self.errors``。"""
        if not self._servers:
            return self.errors

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, name="jlagent-mcp", daemon=True
        )
        self._thread.start()

        failures: list[str] = []
        for config in self._servers:
            ready: concurrent.futures.Future[_ServerState] = concurrent.futures.Future()
            asyncio.run_coroutine_threadsafe(self._serve(config, ready), self._loop)
            try:
                state = ready.result(timeout=self._timeout)
            except concurrent.futures.TimeoutError:
                failures.append(
                    f"MCP Server '{config.name}' 连接超时（{self._timeout:g} 秒）"
                )
                continue

            if state.error:
                failures.append(
                    f"MCP Server '{config.name}' 连接失败：{state.error}"
                )
                continue

            for tool in state.tools:
                self.tools.append(
                    MCPToolInfo(
                        server=config.name,
                        name=str(getattr(tool, "name", "")),
                        description=str(getattr(tool, "description", "") or "").strip(),
                        input_schema=getattr(tool, "input_schema", None) or {},
                    )
                )

        self.errors.extend(failures)
        return self.errors

    def start_async(self, on_update: Callable[[], None] | None = None) -> bool:
        """非阻塞启动：立即返回，后台并发连接各 Server。

        每完成一个 Server 的连接（或失败）即调用 ``on_update``（在后台线程中），
        调用方应在该回调里自行调度 UI 线程刷新。返回是否已启动。
        """
        if self._started or not self._servers:
            return False
        self._started = True

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, name="jlagent-mcp", daemon=True
        )
        self._thread.start()

        futures: list[tuple[MCPServerConfig, concurrent.futures.Future]] = []
        for config in self._servers:
            ready: concurrent.futures.Future[_ServerState] = concurrent.futures.Future()
            asyncio.run_coroutine_threadsafe(self._serve(config, ready), self._loop)
            futures.append((config, ready))

        self._bind_thread = threading.Thread(
            target=self._collect_results,
            args=(futures, on_update),
            name="jlagent-mcp-bind",
            daemon=True,
        )
        self._bind_thread.start()
        return True

    def _collect_results(
        self,
        futures: list[tuple[MCPServerConfig, concurrent.futures.Future]],
        on_update: Callable[[], None] | None,
    ) -> None:
        for config, ready in futures:
            try:
                state = ready.result(timeout=self._timeout)
            except concurrent.futures.TimeoutError:
                self.errors.append(
                    f"MCP Server '{config.name}' 连接超时（{self._timeout:g} 秒）"
                )
            else:
                if state.error:
                    self.errors.append(
                        f"MCP Server '{config.name}' 连接失败：{state.error}"
                    )
                else:
                    self._append_tools(config, state.tools)
            if on_update is not None:
                on_update()

    def _append_tools(self, config: MCPServerConfig, tools: list[Any]) -> None:
        for tool in tools:
            self.tools.append(
                MCPToolInfo(
                    server=config.name,
                    name=str(getattr(tool, "name", "")),
                    description=str(getattr(tool, "description", "") or "").strip(),
                    input_schema=getattr(tool, "input_schema", None) or {},
                )
            )

    def close(self) -> None:
        loop = self._loop
        if loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._shutdown(), loop).result(
                timeout=self._timeout
            )
        except Exception:
            pass
        loop.call_soon_threadsafe(loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=self._timeout)
        try:
            loop.close()
        except Exception:
            pass
        self._loop = None
        self._thread = None

    def _run_loop(self) -> None:
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _shutdown(self) -> None:
        self._stop.set()
        pending = [
            task for task in asyncio.all_tasks() if task is not asyncio.current_task()
        ]
        if not pending:
            return
        try:
            await asyncio.wait_for(
                asyncio.gather(*pending, return_exceptions=True),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            pass

    # ---- 连接与工具发现 -------------------------------------------------
    async def _serve(
        self, config: MCPServerConfig, ready: concurrent.futures.Future[_ServerState]
    ) -> None:
        state = _ServerState()
        errlog = _open_errlog(config.transport)
        try:
            async with self._streams(config, errlog) as streams:
                async with ClientSession(
                    streams[0], streams[1], read_timeout_seconds=self._timeout
                ) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    state.session = session
                    state.tools = list(result.tools)
                    self._sessions[config.name] = session
                    if not ready.done():
                        ready.set_result(state)
                    await self._stop.wait()
        except Exception as error:
            state.error = _describe_error(error)
            stderr = _read_tail(errlog)
            if stderr:
                state.error = f"{state.error}（服务端 stderr：{stderr}）"
        finally:
            _close(errlog)
            self._sessions.pop(config.name, None)
            if not ready.done():
                ready.set_result(state)

    @asynccontextmanager
    async def _streams(self, config: MCPServerConfig, errlog):
        if config.transport == "stdio":
            params = StdioServerParameters(
                command=config.command,
                args=list(config.args),
                env=config.env or None,
                cwd=config.cwd or None,
            )
            async with stdio_client(
                params, errlog=errlog or sys.stderr
            ) as streams:
                yield streams
            return

        client = create_mcp_http_client(headers=config.headers or None)
        try:
            async with streamable_http_client(config.url, http_client=client) as streams:
                yield streams
        finally:
            await client.aclose()

    # ---- 工具调用 -------------------------------------------------------
    def bind(self, exposed: str, info: MCPToolInfo) -> None:
        """记录 LLM 可见名称 -> 具体 Server 工具的映射。"""
        self._tool_map[exposed] = info

    @property
    def bound_tools(self) -> dict[str, MCPToolInfo]:
        return dict(self._tool_map)

    @property
    def connected_servers(self) -> list[str]:
        return sorted(self._sessions)

    @property
    def server_names(self) -> list[str]:
        return [config.name for config in self._servers]

    def invoke(self, exposed: str, arguments: dict[str, Any]) -> str:
        info = self._tool_map.get(exposed)
        if info is None:
            return f"错误：未注册的 MCP 工具 {exposed}"
        if self._loop is None:
            return "错误：MCP 客户端未启动"

        session = self._sessions.get(info.server)
        if session is None:
            detail = _server_error(self.errors, info.server)
            return (
                f"错误：MCP Server '{info.server}' 当前不可用，无法调用 '{info.name}'"
                + (f"（{detail}）" if detail else "")
            )

        future = asyncio.run_coroutine_threadsafe(
            session.call_tool(info.name, arguments or None), self._loop
        )
        try:
            result = future.result(timeout=self._timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            return (
                f"错误：调用 MCP 工具 '{info.name}'（{info.server}）"
                f"超时（{self._timeout:g} 秒）"
            )
        except Exception as error:
            return (
                f"错误：调用 MCP 工具 '{info.name}'（{info.server}）失败："
                f"{_describe_error(error)}"
            )
        return _format_result(result)


def _server_error(errors: list[str], server: str) -> str:
    prefix = f"MCP Server '{server}'"
    for line in errors:
        if line.startswith(prefix):
            return line
    return ""
