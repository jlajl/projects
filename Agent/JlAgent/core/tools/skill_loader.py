from pathlib import Path

from ..skills import Skill, SkillCatalog
from .base import Tool

# 单次读取的内容上限：技能说明可能很长，超出部分不直接灌进上下文，
# 由模型改用 filename 精确读取需要的文件。
MAX_CONTENT_CHARS = 20000


def _read_text(path: Path, title: str, max_chars: int = MAX_CONTENT_CHARS) -> str:
    try:
        content = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return f"错误：{title} 不是 UTF-8 文本文件"
    except OSError as error:
        return f"错误：无法读取 {title}：{error}"
    if max_chars > 0 and len(content) > max_chars:
        content = (
            f"{content[:max_chars]}\n\n"
            f"…（内容已截断，完整文件共 {len(content)} 字符，上限 {max_chars}。"
            "需要其余部分时请用 filename 读取具体文件）"
        )
    return f"{title}:\n\n{content}"


def _resolve(
    skill: Skill, filename: str, project_root: Path
) -> tuple[Path | None, str]:
    skill_dir = skill.directory
    candidate = Path(filename)

    if candidate.is_absolute():
        resolved = candidate.resolve()
        if not resolved.is_relative_to(skill_dir):
            return None, "错误：不允许访问该 Skill 目录之外的文件"
        if resolved.is_file():
            return resolved, ""
        return None, f"错误：文件不存在 {filename}"

    exact = (skill_dir / candidate).resolve()
    if exact.is_file() and exact.is_relative_to(skill_dir):
        return exact, ""
    if exact.exists() and not exact.is_relative_to(skill_dir):
        return None, "错误：不允许访问该 Skill 目录之外的文件"

    project_path = (project_root / candidate).resolve()
    if project_path.is_file() and project_path.is_relative_to(skill_dir):
        return project_path, ""

    if candidate.parent != Path("."):
        return None, f"错误：文件不存在 {filename}"

    matches = sorted(
        path
        for path in skill_dir.rglob(candidate.name)
        if path.is_file() and path.resolve().is_relative_to(skill_dir)
    )
    if len(matches) == 1:
        return matches[0].resolve(), ""
    if matches:
        candidates = "\n".join(
            f"- {path.relative_to(skill_dir).as_posix()}" for path in matches
        )
        return (
            None,
            f"错误：文件名 '{filename}' 在 Skill '{skill.name}' 中匹配到多个文件，"
            f"请指定以下候选路径之一：\n{candidates}",
        )
    return None, f"错误：在 Skill '{skill.name}' 中未找到文件 {filename}"


def build_tools(catalog: SkillCatalog) -> list[Tool]:
    def load_skill(name: str, filename: str = "") -> str:
        if not isinstance(name, str) or not name.strip():
            return "错误：Skill 名称不能为空"
        if filename is None:
            filename = ""
        if not isinstance(filename, str):
            return "错误：filename 必须是字符串"

        skill = catalog.get(name.strip())
        if skill is None:
            available = ", ".join(item.name for item in catalog.skills) or "无"
            return f"错误：未找到 Skill '{name}'。可用 Skill：{available}"

        filename = filename.strip()
        if not filename:
            return _read_text(
                skill.directory / "SKILL.md", f"Skill '{skill.name}'（SKILL.md）"
            )

        resolved, error = _resolve(skill, filename, catalog.project_root)
        if error:
            return error
        relative = resolved.relative_to(skill.directory).as_posix()
        return _read_text(resolved, f"Skill '{skill.name}' 文件 '{relative}'")

    return [
        Tool(
            "loadSkill",
            "加载指定 Skill 的完整说明或其中引用的附加文件。"
            "仅提供 name 时读取 SKILL.md；同时提供 filename 时读取该 Skill 目录内的对应文件。",
            {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Skill 名称",
                    },
                    "filename": {
                        "type": "string",
                        "description": "可选，附加文件的相对路径、项目相对路径或绝对路径",
                    },
                },
                "required": ["name"],
            },
            load_skill,
        )
    ]
