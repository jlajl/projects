# 课程项目合集

本仓库包含三次课程开发的代码项目。

## 项目列表

| 项目 | 目录 | 说明 |
|------|------|------|
| AnythingLLMServer | `AnythingLLMServer/` | 调用 AnythingLLM API 上传文档并完成向量化嵌入的前端页面 |
| AnythingLLMMCP | `AnythingLLMMCP/` | AnythingLLM 的 MCP Server，封装文档管理接口为 MCP Tool |
| PetHospitalMCP | `PetHospitalMCP/` | 宠物医院 REST API 的 MCP Server，提供 11 个宠物管理工具 |

## 技术栈

- **前端**：HTML / CSS / JavaScript
- **后端**：Python / FastAPI
- **AI 工具链**：MCP (Model Context Protocol)、AnythingLLM Document API

## 目录结构

```
.
├── AnythingLLMServer/    # 文档上传前端
│   └── index.html
├── AnythingLLMMCP/       # AnythingLLM MCP Server
│   ├── server.py
│   ├── requirements.txt
│   └── .mcp.json
└── PetHospitalMCP/       # 宠物医院 MCP Server
    └── mcp/
        ├── server.py
        ├── client.py
        ├── requirements.txt
        └── .env.example
```
