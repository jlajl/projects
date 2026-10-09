# 宠物医院 MCP Server

把 [宠物医院 REST API](../README.md) 包装成 11 个 MCP tool，供 AI agent（Claude Desktop、Cursor 等）通过 MCP 协议操作。

## 架构

```
AI agent ──MCP/stdio──> server.py ──HTTP──> pethospital (127.0.0.1:8080)
                         (Python)                  (Go REST + 自实现 DB)
```

- 语言：Python 3.10+
- SDK：官方 `mcp` 包 v1.17.0（`from mcp.server.fastmcp import FastMCP`），stdio transport
- 零额外 HTTP 依赖：用标准库 `urllib`，不引入 requests
- 不改动现有 Go 代码，仅通过 REST 调用

## 前置条件

1. **先启动 pethospital REST 服务**（见项目根 README）：
   ```bash
   cd ..            # 到 pet-hospital-mcp-teaching-main 根目录
   go run . -seed   # 启动并写入 8 条手工 + 1000 条随机数据
   ```
   确认 `http://127.0.0.1:8080/health` 可访问。

2. **装 MCP 依赖**：
   ```bash
   pip install -r requirements.txt
   ```

## 运行 MCP server

```bash
# 默认连 http://127.0.0.1:8080
python server.py

# 指定其他地址
PET_HOSPITAL_URL=http://127.0.0.1:9090 python server.py
```

stdio transport，单独运行不输出内容（等 MCP 客户端连），属正常现象。

## 11 个 tool

| tool | 说明 | REST |
| --- | --- | --- |
| `get_stats(top=5)` | 医院经营统计 | GET /api/v1/stats |
| `list_pets(...)` | 档案列表（过滤+排序+分页） | GET /api/v1/pets |
| `get_pet(id)` | 按 ID 查宠物 | GET /api/v1/pets/{id} |
| `create_pet(...)` | 新增档案（id 自动生成） | POST /api/v1/pets |
| `update_pet(id, fields)` | 局部更新（PATCH） | PATCH /api/v1/pets/{id} |
| `delete_pet(id)` | 删除档案 | DELETE /api/v1/pets/{id} |
| `search_pets(q)` | 全文检索 | GET /api/v1/pets/search |
| `add_medical_record(id, ...)` | 追加病历 | POST /api/v1/pets/{id}/records |
| `add_charge(id, item, category, amount, ...)` | 追加收费 | POST /api/v1/pets/{id}/charges |
| `get_pet_summary(id)` | 单只宠物费用与就诊汇总 | GET /api/v1/pets/{id}/summary |
| `seed_data(count=1000, force=False)` | 写入模拟数据 | POST /api/v1/admin/seed |

> 运维操作（压实数据库）不暴露为 tool，直接 `curl -X POST http://127.0.0.1:8080/api/v1/admin/compact`。

## 验证

### 方式一：MCP Inspector（推荐，交互测试）

```bash
npx @modelcontextprotocol/inspector python server.py
```

浏览器打开提示的 URL → 左侧列出 11 个 tool → 点 `get_stats` 调用 → 右侧看到 JSON 数据即链路通。

### 方式二：Claude Desktop

编辑配置文件（macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "宠物医院": {
      "command": "python",
      "args": [
        "D:/Project/pet-hospital-mcp-teaching-main/pet-hospital-mcp-teaching-main/mcp/server.py"
      ],
      "env": {
        "PET_HOSPITAL_URL": "http://127.0.0.1:8080"
      }
    }
  }
}
```

重启 Claude Desktop，对话测试：
- 「列出消费前 5 的宠物」→ 触发 `get_stats`
- 「新增一只叫旺财的金毛，主人张三电话13800001111，医生李医生，急性肠胃炎」→ 触发 `create_pet`
- 「PET-000001 的就诊汇总」→ 触发 `get_pet_summary`

## 错误处理

REST 非 200 / 网络异常 / 库不存在时，`PetHospitalError` 会被 FastMCP 回传给 LLM，LLM 可看到错误文本并据此重试或改参数。例如未启动 pethospital 时调任意 tool 会得到「无法连接宠物医院 REST 服务…先启动 pethospital」。
