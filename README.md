# 课程项目合集

本仓库包含《LLM 技术与应用》课程的四个交付模块：两个 MCP Server、一个网页前端、一个定制 Agent，
另有两个课堂练习项目。

## 项目地图

| 项目 | 目录 | 说明 | 详细文档 |
|---|---|---|---|
| A 宠物医院 MCP | `PetHospitalMCP/mcp/` | 把宠物医院 REST 服务包装成 11 个 MCP tool（stdio） | [README](PetHospitalMCP/mcp/README.md) |
| B AnythingLLM MCP | `AnythingLLMMCP/` | 把 AnythingLLM 的对话与文档查询封装成 MCP tool（Streamable HTTP） | [README](AnythingLLMMCP/README.md) |
| C AnythingLLM 网页 | `AnythingLLMServer/` | 单文件网页，上传文档并触发向量化嵌入 | [README](AnythingLLMServer/README.md) |
| D 定制 Agent | `Agent/JlAgent/` | 本地文件/检索 Agent：TUI、技能、MCP 客户端、AGENTS.md、上下文压缩 | [README](Agent/JlAgent/README.md) |
| 课堂练习 | `Agent/Practice01/`、`Agent/Practice02/` | 流式对话脚本、工具调用练手项目 | [README](Agent/Practice02/README.md) |

模块关系：

```
AnythingLLM 网页(C) ──HTTP──> AnythingLLM :3001
AnythingLLM MCP(B) ──MCP/HTTP──> AnythingLLM :3001
宠物医院 MCP(A) ──HTTP──> pethospital REST :8080
定制 Agent(D) ──MCP──> 任意 MCP Server（含 A/B）
             └──HTTP──> OpenAI 兼容模型服务 :1234
```

## 目录结构

```
.
├── README.md
├── .gitignore
├── AnythingLLMServer/          # C：文档上传前端
│   ├── index.html
│   ├── config.example.js       # 密钥模板（复制为 config.js，已被忽略）
│   └── README.md
├── AnythingLLMMCP/             # B：AnythingLLM MCP Server
│   ├── server.py
│   ├── .mcp.json
│   ├── .env.example
│   ├── requirements.txt
│   └── README.md
├── PetHospitalMCP/             # A：宠物医院 MCP Server
│   ├── mcp/
│   │   ├── server.py
│   │   ├── client.py
│   │   ├── .env.example
│   │   ├── requirements.txt
│   │   └── README.md
│   ├── pet-hospital-mcp-teaching-main/   # 课程提供的 REST 服务源码
│   └── pet-hospital-windows-amd64/       # 课程提供的 REST 发行包
└── Agent/
    ├── .mcp.json               # Agent 的 MCP 配置示例
    ├── JlAgent/                # D：定制 Agent（见其 README）
    ├── Practice01/             # 流式对话练习
    └── Practice02/             # 工具调用练习（11 工具 + 架构图）
```

## 环境依赖

| 依赖 | 版本 | 适用模块 |
|---|---|---|
| Python | 3.10+（实际开发环境 3.13） | A / B / D |
| `mcp` | A：`>=1.17.0,<2.0`；B：`>=2.2.0`；D：`>=2.0` | A / B / D |
| `httpx` / `openai` / `textual` / `trafilatura` / `PyYAML` | 见各模块 `requirements.txt` | B / D |
| AnythingLLM | 运行于 `http://localhost:3001` | B / C |
| pethospital REST | Windows 可直接用发行包的 `pethospital.exe`，无需 Go | A |
| LM Studio（或任意 OpenAI 兼容服务） | 供 D 使用，默认 `http://127.0.0.1:1234/v1` | D |

## 配置与密钥

所有密钥都**不入库**，仓库只提交 `*.example` 模板；真实配置写在被 `.gitignore` 忽略的文件里。

| 模块 | 配置文件 | 模板 | 关键字段 |
|---|---|---|---|
| A | 环境变量 `PET_HOSPITAL_URL` | `PetHospitalMCP/mcp/.env.example` | REST 地址，默认 `http://127.0.0.1:8080` |
| B | 环境变量 `ANYTHINGLLM_URL` / `ANYTHINGLLM_API_KEY` | `AnythingLLMMCP/.env.example` | 服务地址、API Key |
| C | `AnythingLLMServer/config.js` | `config.example.js` | `apiBase`、`apiKey` |
| D | `Agent/JlAgent/config.ini`（首次运行自动生成） | 代码内置模板 `core/config.py` | 模型地址/密钥、workspace、max_steps 等 |

## 分步启动

```bash
# A 宠物医院 MCP：先起 REST，再让 MCP 客户端拉起 MCP Server
cd PetHospitalMCP/mcp
python -m pip install -r requirements.txt
# 另开一个终端：../pet-hospital-windows-amd64/windows/pethospital.exe
npx @modelcontextprotocol/inspector python server.py     # 验证 11 个 tool 可枚举

# B AnythingLLM MCP
cd AnythingLLMMCP
python -m pip install -r requirements.txt
$env:ANYTHINGLLM_API_KEY="<你的 Key>"                     # bash: export ...
python server.py                                          # 监听 8001/mcp

# C AnythingLLM 网页
cd AnythingLLMServer
cp config.example.js config.js                             # 填入 apiKey
python -m http.server 8000                                 # 打开 127.0.0.1:8000

# D 定制 Agent
cd Agent/JlAgent
python -m pip install -r requirements.txt
python run.py                                              # 首次会生成 config.ini，填好模型信息后重启
```

## 验证

| 模块 | 验证方式 | 期望结果 |
|---|---|---|
| A | MCP Inspector 连接 `python server.py` | 左侧列出 11 个 tool，调 `get_stats` 返回 JSON |
| B | MCP Inspector 连 `http://127.0.0.1:8001/mcp` | 列出 `chat`、`list_documents` 两个工具 |
| C | 打开页面 | 显示第一个工作区名称；选文件上传后显示标题/词数/token |
| D | `python -m unittest discover -s tests -v` | 10 个用例全部 ok |
| D | `python scripts/validate_skills.py` | 1 个 Skill 通过（0 失败） |

## 第三方材料声明

`PetHospitalMCP/pet-hospital-mcp-teaching-main/`、`PetHospitalMCP/pet-hospital-windows-amd64/`
以及 `PetHospitalMCP/mcp/` 中的 `server.py` / `client.py` 来自课程提供的教学仓库，随仓库一并提交以便复现；
`mcp/README.md` 为在本仓库内重写的使用说明。除此之外的代码为本仓库自行编写。
