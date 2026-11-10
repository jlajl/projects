import re
from pathlib import Path

from ..skills import SkillCatalog
from .base import Tool


_VALID_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _normalize_name(raw: str) -> tuple[str, str]:
    """将原始名称规范化为小写字母/数字/连字符格式。

    返回 (normalized_name, error_message)；error_message 为空表示成功。
    """
    if not isinstance(raw, str) or not raw.strip():
        return "", "错误：Skill 名称不能为空"

    lowered = raw.strip().lower()
    replaced = re.sub(r"[^a-z0-9]+", "-", lowered)
    collapsed = re.sub(r"-+", "-", replaced).strip("-")

    if not collapsed:
        return "", f"错误：Skill 名称 '{raw}' 规范化后为空"

    if not _VALID_NAME.match(collapsed):
        return "", f"错误：Skill 名称 '{raw}' 规范化后 '{collapsed}' 不符合规范"

    return collapsed, ""


def _looks_like_skill_md(content: str) -> str:
    """对 skillContext 做最基本的格式校验，返回错误信息（空字符串表示通过）。"""
    if not isinstance(content, str) or not content.strip():
        return "错误：skillContext 不能为空"

    text = content.lstrip("\ufeff").lstrip()
    if not text.startswith("---"):
        return (
            "错误：skillContext 必须以 YAML frontmatter 开头（即第一行为 '---'），"
            "需包含 name 与 description 字段。"
        )
    return ""


def build_tools(workspace: Path, skill_catalog: SkillCatalog | None) -> list[Tool]:
    root = workspace.resolve()

    def create_skill(name: str, skillContext: str) -> str:
        normalized, error = _normalize_name(name)
        if error:
            return error

        error = _looks_like_skill_md(skillContext)
        if error:
            return error

        skills_dir = root / ".agents" / "skills"
        skill_dir = skills_dir / normalized
        skill_file = skill_dir / "SKILL.md"

        # 先通过 SkillCatalog 检测（覆盖已发现但未刷新的场景）
        if skill_catalog is not None:
            existing = skill_catalog.get(normalized)
            if existing is not None:
                return (
                    f"错误：Skill '{normalized}' 已存在（目录 {existing.directory}），"
                    "如需更新请先手动删除或改用其他名称"
                )

        # 再检查文件系统，覆盖目录已建但 catalog 未加载的情况
        if skill_dir.exists() or skill_file.is_file():
            return (
                f"错误：目标目录 {skill_dir} 已存在，"
                "为避免意外覆盖，请改用其他名称或由用户确认后再操作"
            )

        try:
            skills_dir.mkdir(parents=True, exist_ok=True)
            skill_dir.mkdir(parents=True, exist_ok=False)
            skill_file.write_text(skillContext, encoding="utf-8")
        except OSError as exc:
            return f"错误：创建 Skill 失败：{exc}"

        return (
            f"已创建 Skill '{normalized}'：{skill_file}\n"
            "如需添加 references/、scripts/ 等辅助目录或其他文件，可继续调用文件操作工具完成。"
        )

    return [
        Tool(
            "createSkill",
            (
                "根据自然语言要求创建一个新的 Skill。"
                "在项目 .agents/skills/ 下创建以 skill 名称命名的子目录并写入 SKILL.md。"
                "Skill 名称统一采用小写字母、数字与连字符的格式。"
                "如果目标 Skill 已存在，将返回明确提示以避免覆盖。"
                "创建 references/、scripts/ 等辅助目录请继续使用文件操作工具。"
            ),
            {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": (
                            "Skill 名称，最终会被规范化为小写字母、数字与连字符组成的格式 "
                            "（例如 'My Skill' 会变成 'my-skill'）。"
                        ),
                    },
                    "skillContext": {
                        "type": "string",
                        "description": (
                            "要写入 SKILL.md 的完整内容，必须以 YAML frontmatter 开头 "
                            "（首行 '---'，内含 name 与 description 字段，以 '---' 结尾），"
                            "frontmatter 之后为 Markdown 正文。"
                        ),
                    },
                },
                "required": ["name", "skillContext"],
            },
            create_skill,
        )
    ]
