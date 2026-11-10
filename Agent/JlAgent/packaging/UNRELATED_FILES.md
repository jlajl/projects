# JlAgent 目录中与 Agent 核心代码无关的文件清单

生成时间：2026-11-04
扫描目录：d:\study\Projects\Agent\JlAgent

## 判定标准

**与 Agent 相关**：运行时必须存在的源码（.py / .tcss）、运行时配置（config.ini / .mcp.json / requirements.txt）、技能（.agents/skills）。

**与 Agent 无关**：一次性脚本、第三方工具残留、构建生成产物、临时文档、字节码缓存等；删除后不影响 Agent 功能。

---

## A. 完全无关（建议移出项目或删除）

### 一次性辅助脚本（与 Agent 业务无关）
- `create_docx.py` — 生成"12月31日放假通知" docx 的一次性脚本，Agent 核心未引用

### 临时产物
- `december_31_holiday_notification.txt` — 放假通知脚本产物
- `december_31_holiday_report.txt` — 放假报告脚本产物

### UnifyPy 打包工具的状态目录（不属于本项目，只是工具运行产生的残留）
- `.unifypy/` — UnifyPy 的缓存与元数据（cache / metadata.json / .gitignore）
- `.unifypy_rollback/` — UnifyPy 打包前的回滚快照（operations_*.json / backup_* / .gitignore）

## B. 构建生成产物（可随构建重新生成，不必纳入版本控制）

### PyInstaller / UnifyPy 构建输出
- `JlAgent.spec` — PyInstaller 自动生成的 spec 文件（build_package.bat 每次都会删除重建）
- `build/` — PyInstaller 中间产物目录（Analysis-00.toc / PYZ-00.pyz / localpycs/*.pyc / warn-JlAgent.txt / xref-JlAgent.html 等）
- `dist/JlAgent.exe` — 打包出的单文件 exe

### Inno Setup 安装包
- `installer/JlAgent-1.0.0-x86_64.exe` — 安装包产物

## C. Python 字节码缓存（随时可删）

所有 `__pycache__/` 目录及其中的 `*.pyc` 文件：
- `__pycache__/run.cpython-313.pyc`
- `core/__pycache__/*.pyc`（10 个）
- `core/tools/__pycache__/*.pyc`（11 个）
- `tui/__pycache__/*.pyc`（4 个）

## D. 打包相关但可选（与 Agent 运行无关，但打包时需要）

以下文件不属于 Agent 运行时必需，但被 `build_package.bat` 引用：
- `build_package.bat` — 一键打包脚本
- `build.json` — UnifyPy 打包配置（入口、hidden_import、数据文件等）
- `打包说明.md` — 打包流程说明文档

如果项目不再提供 exe 分发，以上三项也可一并移出。

---

## 保留（与 Agent 直接相关，不应动）

| 路径 | 用途 |
| --- | --- |
| `run.py` / `core/*.py` / `core/tools/*.py` / `tui/*.py` / `tui/app.tcss` | Agent 核心源码 |
| `config.ini` | 运行时配置（首次启动自动生成） |
| `requirements.txt` | Python 依赖 |
| `.agents/skills/miniencryption/SKILL.md` | 用户提供的示例 Skill（属 Agent 技能体系） |

## 建议

1. 把 A 类（完全无关）移到项目外的一个归档目录，或直接删除。
2. 把 B、C 类加入 `.gitignore`，避免污染版本库。
3. D 类视是否保留打包流程决定；若放弃 exe 分发，也可一并归档。
