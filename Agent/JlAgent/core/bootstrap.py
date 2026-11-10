import atexit
from pathlib import Path

from .agent import Agent
from .config import Config
from .llm import LLMClient
from .mcp_client import MCPClientManager, find_config_file, load_servers
from .skills import SkillCatalog, build_system_prompt
from .tools import build_registry


def create_agent(
    config: Config,
    skill_catalog: SkillCatalog | None = None,
    mcp_manager: MCPClientManager | None = None,
) -> Agent:
    catalog = (
        skill_catalog
        if skill_catalog is not None
        else SkillCatalog.discover(config.workspace, config.skills_dir)
    )
    manager = (
        mcp_manager
        if mcp_manager is not None
        else create_mcp_manager(config.workspace, config.mcp_timeout)
    )
    llm = LLMClient(config.api_key, config.base_url, config.model_name)

    context_window = config.context_window
    known = context_window is not None and context_window > 0
    if not known:
        context_window, known = llm.context_window()

    agent = Agent(
        llm,
        build_registry(
            config.workspace,
            config.baidu_search_api_key,
            catalog,
            manager,
            search_request_timeout=config.search_request_timeout,
            search_max_results=config.search_max_results,
            search_snippet_limit=config.search_snippet_limit,
            search_answer_limit=config.search_answer_limit,
            web_request_timeout=config.web_request_timeout,
            web_max_content_chars=config.web_max_content_chars,
            cli_exec_timeout=config.cli_exec_timeout,
            cli_max_stream_chars=config.cli_max_stream_chars,
        ),
        system_prompt=build_system_prompt(config.system_prompt, catalog),
        max_steps=config.max_steps,
        mcp_manager=manager,
        workspace=config.workspace,
        context_window=context_window,
        context_window_known=known,
    )
    inject_agents_md(agent, config.workspace)
    return agent


def create_mcp_manager(
    workspace: Path, timeout: float = 30.0
) -> MCPClientManager | None:
    """读取当前项目目录下的 ``.mcp.json`` 并构造 MCP 客户端（不阻塞启动）。

    没有配置文件时返回 None。连接由调用方通过 ``start_async`` 在后台完成，
    连接过程中与完成后的错误记录在 ``manager.errors`` 中。
    """
    path = find_config_file(Path.cwd(), workspace)
    if path is None:
        return None

    servers, errors = load_servers(path)
    manager = MCPClientManager(servers, timeout=timeout, config_path=path)
    manager.errors.extend(errors)
    atexit.register(manager.close)
    return manager


def bind_mcp_tools(agent: Agent) -> int:
    """把已经发现的 MCP 工具注册进 Agent 的工具表，返回本次新增数量。"""
    from .tools import mcp_tools

    manager = agent.mcp_manager
    if manager is None or not manager.tools:
        return 0
    existing = {tool.name for tool in agent.tools}
    new_tools = mcp_tools.build_tools(manager, existing)
    agent.add_tools(new_tools)
    return len(new_tools)


def read_agents_md(workspace: Path) -> str | None:
    """读取项目目录下的 AGENTS.md，不存在或为空返回 None。"""
    path = workspace / "AGENTS.md"
    if not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return None
    return content or None


def inject_agents_md(agent: Agent, workspace: Path) -> bool:
    """把 AGENTS.md 注入会话（仅在首次加载时，一次注入全程复用）。"""
    content = read_agents_md(workspace)
    if content is None:
        return False
    return agent.inject_agents_md(content)