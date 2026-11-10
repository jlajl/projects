"""配置加载：从当前目录的 ``config.ini`` 读取运行参数，缺失时自动生成。

所有参数都有默认值，用户可只填写关心的部分；建议完整保留生成文件中的注释。
"""

from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILENAME = "config.ini"

# 各分组默认值（与 config.ini 的 section 一一对应）
DEFAULTS = {
    "llm": {
        "api_key": "lm-studio",
        "base_url": "http://127.0.0.1:1234/v1",
        "model_name": "qwen2.5-7b-instruct",
        "context_window": "",
    },
    "agent": {
        "workspace": ".",
        "max_steps": "8",
        "skills_dir": ".agents/skills",
        "system_prompt": "",
        "agents_file": "AGENTS.md",
        "agents_md_max_chars": "8000",
    },
    "search": {
        "baidu_api_key": "",
        "request_timeout": "20",
        "max_results": "8",
        "snippet_limit": "300",
        "answer_limit": "1500",
    },
    "mcp": {"timeout": "30"},
    "cli": {"exec_timeout": "30", "max_stream_chars": "4000"},
    "web": {"request_timeout": "20", "max_content_chars": "8000"},
}

DEFAULT_SYSTEM_PROMPT = (
    "你是一个本地文件与信息检索助手，可以查看、创建、编辑、删除文件和目录。"
    "遇到实时新闻、近期事件或需要联网核实的问题时，先调用 searchWeb 搜索，"
    "再用 fetchWeb 阅读具体网页。需要运行本地命令行程序、查看环境或执行脚本时，"
    "调用 RunCLI。执行操作前先确认路径，收到工具结果后简洁地告知用户结果。"
)


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str
    model_name: str
    workspace: Path
    system_prompt: str
    max_steps: int
    baidu_search_api_key: str
    context_window: int | None = None
    # 以下为从 config.ini 读取、带默认值的运行参数
    mcp_timeout: float = 30.0
    skills_dir: str = ".agents/skills"
    search_request_timeout: int = 20
    search_max_results: int = 8
    search_snippet_limit: int = 300
    search_answer_limit: int = 1500
    web_request_timeout: int = 20
    web_max_content_chars: int = 8000
    cli_exec_timeout: int = 30
    cli_max_stream_chars: int = 4000
    # 长期规则文件名（自动兼容 AGENTS.md / AGENT.md）与注入时的长度上限
    agents_file: str = "AGENTS.md"
    agents_md_max_chars: int = 8000


def default_config_path() -> Path:
    """运行时配置一律从当前工作目录读取。"""
    return Path.cwd() / CONFIG_FILENAME


def _resolve_workspace(raw: str) -> Path:
    configured = Path(raw or DEFAULTS["agent"]["workspace"])
    workspace = configured if configured.is_absolute() else Path.cwd() / configured
    return workspace.resolve()


def load_config(path: Path | str | None = None) -> Config:
    config_path = Path(path) if path else default_config_path()
    parser = ConfigParser()
    if not parser.read(config_path, encoding="utf-8"):
        raise FileNotFoundError(f"找不到配置文件 {config_path}")

    def _section(name: str) -> dict[str, str]:
        merged = dict(DEFAULTS[name])
        if parser.has_section(name):
            for key, value in parser.items(name):
                merged[key] = value
        return merged

    llm = _section("llm")
    agent = _section("agent")
    search = _section("search")
    mcp = _section("mcp")
    cli = _section("cli")
    web = _section("web")

    context_window_raw = llm["context_window"].strip()
    context_window = int(context_window_raw) if context_window_raw.isdigit() else None

    return Config(
        api_key=llm["api_key"].strip(),
        base_url=llm["base_url"].strip(),
        model_name=llm["model_name"].strip(),
        workspace=_resolve_workspace(agent["workspace"]),
        system_prompt=agent["system_prompt"] or DEFAULT_SYSTEM_PROMPT,
        max_steps=_get_int(agent["max_steps"], 8),
        baidu_search_api_key=search["baidu_api_key"].strip(),
        context_window=context_window,
        mcp_timeout=_get_float(mcp["timeout"], 30.0),
        skills_dir=agent["skills_dir"].strip() or ".agents/skills",
        search_request_timeout=_get_int(search["request_timeout"], 20),
        search_max_results=_get_int(search["max_results"], 8),
        search_snippet_limit=_get_int(search["snippet_limit"], 300),
        search_answer_limit=_get_int(search["answer_limit"], 1500),
        web_request_timeout=_get_int(web["request_timeout"], 20),
        web_max_content_chars=_get_int(web["max_content_chars"], 8000),
        cli_exec_timeout=_get_int(cli["exec_timeout"], 30),
        cli_max_stream_chars=_get_int(cli["max_stream_chars"], 4000),
        agents_file=agent["agents_file"].strip() or "AGENTS.md",
        agents_md_max_chars=_get_int(agent["agents_md_max_chars"], 8000),
    )


def _get_int(raw: str, default: int) -> int:
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def _get_float(raw: str, default: float) -> float:
    try:
        return float(str(raw).strip())
    except ValueError:
        return default


def ensure_config(path: Path | str | None = None) -> tuple[Config, bool]:
    """确保配置文件存在；缺失时生成完整模板，返回 (Config, 是否新建)。"""
    config_path = Path(path) if path else default_config_path()
    created = False
    if not config_path.is_file():
        write_default_config(config_path)
        created = True
    return load_config(config_path), created


def write_default_config(path: Path | str) -> None:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_TEMPLATE, encoding="utf-8")


_TEMPLATE = """# ===============================================================
# JlAgent 配置文件（此文件由程序自动生成，请按需修改后重新启动）
# ---------------------------------------------------------------
# 首次启动会生成此文件并填入占位信息。请修改 [llm] 中的
# api_key / base_url / model_name 等，保存后重新启动才能正常工作。
# 大部分参数都有默认值，保留为空即使用默认值。
# ===============================================================

[llm]
# 模型服务的 API Key（LM Studio 本地服务通常填 lm-studio）
api_key = lm-studio
# 模型服务地址（OpenAI 兼容接口）
base_url = http://127.0.0.1:1234/v1
# 模型名称
model_name = qwen2.5-7b-instruct
# 上下文窗口大小（Token），留空则启动时自动探测，探测失败按 128k 处理并显示「默认」
context_window =

[agent]
# 工作目录（相对路径基于程序启动目录）
workspace = .
# 单次对话最多连续调用工具/模型的轮数
max_steps = 8
# 技能目录（相对项目根目录）
skills_dir = .agents/skills
# 系统提示词，留空使用内置默认提示词
system_prompt =
# 长期规则文件名（留空则只用默认名），自动兼容 AGENTS.md / AGENT.md
agents_file = AGENTS.md
# 注入的长期规则最大字符数，超出部分截断（0 表示不截断）
agents_md_max_chars = 8000

[search]
# 百度智能云搜索 API Key（留空则禁用联网搜索）
baidu_api_key =
request_timeout = 20
max_results = 8
snippet_limit = 300
answer_limit = 1500

[mcp]
# MCP Server 连接与调用超时（秒）
timeout = 30

[cli]
# 本地命令执行超时（秒）
exec_timeout = 30
# 单次返回的最大字符数
max_stream_chars = 4000

[web]
# 网页抓取超时（秒）
request_timeout = 20
# 网页正文最大保留字符数
max_content_chars = 8000
"""