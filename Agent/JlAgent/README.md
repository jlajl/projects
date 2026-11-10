# JlAgent · 本地文件与信息检索 Agent

一个可自带技能、可接入 MCP Server 的本地 Agent：TUI 交互、十类文件/目录操作、联网搜索与网页读取、
上下文压缩与恢复、AGENTS.md 长期规则注入。

## 目录结构

```
JlAgent/
├── run.py                    # 入口：python run.py [tui]
├── config.ini                # 运行时配置（首次启动自动生成，已被 .gitignore 忽略）
├── requirements.txt          # 依赖清单
├── core/                     # 内核（与界面无关）
│   ├── agent.py              # 工具调用主循环、最大步数、上下文压缩
│   ├── llm.py                # OpenAI 兼容客户端、token 用量、上下文窗口探测
│   ├── config.py             # config.ini 解析与默认值（含生成模板）
│   ├── bootstrap.py          # 组装 Agent、读取/注入 AGENTS.md、绑定 MCP 工具
│   ├── mcp_client.py         # MCP 客户端：stdio + streamable HTTP、工具发现、失败降级
│   ├── context.py            # 上下文归档 / token 估算 / 压缩 Prompt / 归档检索
│   ├── skills.py             # 技能扫描、frontmatter 解析、系统提示词注入
│   ├── session.py            # 会话持久化（保存 / 列表 / 恢复）
│   └── tools/                # 每个文件一类工具，全部返回字符串给模型
│       ├── system.py         # getDate / getCwd / isLeapYear
│       ├── filesystem.py     # 十类文件与目录操作
│       ├── search.py         # 百度千帆搜索 API
│       ├── web_fetch.py      # curl 拉取 + trafilatura 转 Markdown
│       ├── cli.py            # 受控外部命令执行
│       ├── recall.py         # 检索已归档的历史上下文
│       ├── skill_creator.py  # 创建技能（校验命名、拒绝覆盖）
│       ├── skill_loader.py   # 按需加载技能（限定技能目录、内容上限）
│       └── mcp_tools.py      # 把 MCP 工具并入本地工具集（来源标记 + 重名隔离）
├── tui/                      # textual 界面
├── tests/test_smoke.py       # 冒烟测试（无需模型与网络）
├── scripts/validate_skills.py# 技能契约校验脚本
└── packaging/                # UnifyPy + Inno Setup 打包
```

## 安装

```bash
cd Agent/JlAgent
pip install -r requirements.txt
```

依赖：`openai>=1.0`、`textual>=8.0`、`trafilatura>=2.0`、`PyYAML>=6.0`、`mcp>=2.0`。

## 配置

首次运行会在**当前工作目录**生成 `config.ini`（模板见 `core/config.py:158`），改完后重启生效。
`config.ini` 含密钥，已被 `.gitignore` 忽略，不提交。

| 分组 | 键 | 说明 | 默认 |
|---|---|---|---|
| `[llm]` | `api_key` | 模型服务密钥 | `lm-studio` |
| | `base_url` | OpenAI 兼容接口地址 | `http://127.0.0.1:1234/v1` |
| | `model_name` | 模型名 | `qwen2.5-7b-instruct` |
| | `context_window` | 上下文窗口 token，留空则自动探测，失败按 128k 显示「默认」 | 空 |
| `[agent]` | `workspace` | 工作目录，所有文件工具都被限制在此目录内 | `.` |
| | `max_steps` | 单轮最多「模型调用 + 工具执行」轮数 | `8` |
| | `skills_dir` | 技能目录（相对项目根） | `.agents/skills` |
| | `system_prompt` | 系统提示词，留空用内置默认 | 空 |
| | `agents_file` | 长期规则文件名，自动兼容 `AGENTS.md` / `AGENT.md` | `AGENTS.md` |
| | `agents_md_max_chars` | 注入的规则最大字符数，超出截断，`0` 为不截断 | `8000` |
| `[search]` | `baidu_api_key` | 百度千帆搜索 Key，留空则搜索工具直接返回配置提示 | 空 |
| | `request_timeout` / `max_results` / `snippet_limit` / `answer_limit` | 搜索超时、条数、摘要与答案长度 | 20 / 8 / 300 / 1500 |
| `[mcp]` | `timeout` | MCP Server 连接与调用超时（秒） | `30` |
| `[cli]` | `exec_timeout` / `max_stream_chars` | 外部命令超时与输出截断 | 30 / 4000 |
| `[web]` | `request_timeout` / `max_content_chars` | 网页抓取超时与正文截断 | 20 / 8000 |

## 启动与验证

```bash
python run.py            # 或 python run.py tui
```

启动后应看到：左侧聊天区、底部状态栏（上下文占用）、右侧"功能与技能"面板（工具数、技能数、MCP Server 状态）。
验证清单：

1. 输入「列出当前目录」→ 触发 `listDir`，思考块里出现工具调用与结果；
2. 输入「判断 1900 和 2000 是不是闰年」→ 触发 `isLeapYear`，答案分别是 不是 / 是；
3. 输入「/status」→ 显示会话 ID、上下文占用、MCP 连接状态；
4. 输入「/compact」→ 归档原上下文并生成摘要，随后可用「查一下归档里关于 XX 的内容」触发 `recallContext`。

## 界面命令

| 命令 | 作用 |
|---|---|
| `/new` | 新建会话（自动保存当前历史） |
| `/resume` | 列出历史会话并选择恢复 |
| `/save` | 保存当前会话 |
| `/compact` | 压缩上下文（归档原始上下文后替换为摘要） |
| `/clear` | 仅清屏，不动上下文 |
| `/status` / `/help` / `/quit` | 状态、帮助、退出 |

输入 `/` 会弹出命令补全面板（↑↓ 选择、Enter 执行、Esc 取消）。上下文占用达 80% 时普通输入会被暂停，
只接受 `/compact`。

## 工具语义清单

| 语义 | 工具 | 真实副作用 |
|---|---|---|
| 当前工作目录 | `getCwd` | 返回 workspace 的绝对路径 |
| 列出目录 | `listDir` | `iterdir()` 枚举，区分目录/文件 |
| 判断路径类型 | `getFileType` | `exists/is_dir` + 扩展名分类 |
| 读文本 | `readFile` | `read_text(utf-8)`，仅白名单扩展名 |
| 建文件 | `createFile` | `write_text`，已存在则拒绝 |
| 改文本 | `editFile` | `write_text` 覆写 |
| 建目录 | `createDir` | `mkdir(parents=True)` |
| 删目录 | `removeDir` | `shutil.rmtree`，拒绝删工作区/程序目录 |
| 删文件 | `removeFile` | `unlink()` |
| 重命名/移动 | `rename` | `Path.rename`，目标存在则拒绝 |
| 日期时间 | `getDate` | `datetime.now()`，跨平台 |
| 闰年判定 | `isLeapYear` | 4 整除且整百需 400 整除 |
| 联网搜索 | `searchWeb` | POST 百度千帆 `web_search` |
| 读网页 | `fetchWeb` | curl 拉取 + trafilatura 转 Markdown |
| 执行命令 | `RunCLI` | `subprocess.run(cwd=workspace)`，超时即终止 |
| 技能创建/加载 | `createSkill` / `loadSkill` | 落盘 `.agents/skills/<name>/SKILL.md` / 按需读取 |
| 归档检索 | `recallContext` | 在 `.agents/context/*.jsonl` 中做全文匹配 |

所有文件类工具都经过同一个 `resolve()`：越出 `workspace` 的路径直接抛 `ValueError`，
再由 `ToolRegistry.execute` 转成"工具执行失败: 路径超出工作区 …"回给模型。

## 技能（Skills）

- 目录：`.agents/skills/<技能名>/SKILL.md`，文件必须以 YAML frontmatter 开头并闭合，
  含非空 `name` 与 `description`；
- 启动时只把**名称 + 描述**注入系统提示词，模型判断相关后再调 `loadSkill` 读取全文（渐进加载）；
- `loadSkill` 只允许读取该技能目录内的文件，单次内容上限 20000 字符，超出截断并提示用 `filename` 精确读取；
- `createSkill` 会把名称规范化为小写连字符格式，校验 frontmatter、拒绝覆盖同名技能；
- 校验全部技能：`python scripts/validate_skills.py`（纯标准库，退出码 0 = 通过）。

示例技能 `.agents/skills/miniencryption/` 演示了最小可用的 SKILL.md 结构。

## MCP 接入

在项目目录放 `.mcp.json`（本仓库的 `Agent/.mcp.json` 是示例，接的是 `bazi-mcp`）：

```json
{
  "mcpServers": {
    "本地服务": {
      "type": "stdio",
      "command": "python",
      "args": ["path/to/server.py"],
      "env": { "PET_HOSPITAL_URL": "http://127.0.0.1:8080" }
    },
    "远程服务": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:8001/mcp",
      "headers": { "Authorization": "Bearer ${TOKEN}" }
    }
  }
}
```

- 传输：`stdio`（拉起本地进程）与 `streamable-http` 两种；
- 启动时在后台线程并发连接，**不阻塞界面**；单个 Server 失败只记入 `manager.errors`，其余工具照常可用；
- 连接成功后把外部工具并入本地工具集：schema 兜底转成 `{"type":"object","properties":{}}`，
  与本地工具或彼此重名时加 `<server>__` 前缀，描述前加 `[MCP:server]` 来源标记；
- 侧栏按 Server 显示「已连接 · N 个工具」或失败原因，`/status` 汇总连接数与注册数。

## AGENTS.md 长期规则

工作目录下的 `AGENTS.md`（或 `AGENT.md`）会作为一条 `user` 消息**一次性**注入对话开头：

- 文件名可用 `[agent] agents_file` 更换，两种等价命名都兼容；
- 超过 `agents_md_max_chars` 会截断并注明原文长度；
- 文件不存在或为空时不报错，直接跳过；
- 新建会话与恢复会话时都会重新检查一次，已注入过则不会重复（`name="agents_md"` 去重）。

## 测试

```bash
python -m unittest discover -s tests -v
python scripts/validate_skills.py
```

`tests/test_smoke.py` 覆盖闰年规则（含 1900/2000/2100 边界）、`getDate` 非硬编码、十类文件语义的真实副作用、
路径越界拦截、工具异常转错误文本、删除工作区根目录的守卫。全部断言无需模型、网络与 mcp 包。

## 打包

`packaging/` 下为一键打包（UnifyPy 打 exe + Inno Setup 打安装包），说明见 `packaging/打包说明.md`。
注意：`config.ini` 会被打进 exe，其中若含密钥则随安装包分发，请勿公开分发。

## 已知限制

- 单进程单会话，TUI 同一时刻只跑一个任务（`@work(exclusive=True)`）；
- `readFile` 无分页，超大文本会一次性进上下文；
- 只支持 OpenAI 兼容接口，无多 provider 适配与自动降级。
