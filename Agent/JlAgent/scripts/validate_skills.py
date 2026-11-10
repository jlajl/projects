"""校验 .agents/skills 下每个 Skill 是否满足加载契约。

只依赖标准库，可直接在任意机器上跑（不导入 core，避免拉起重依赖）：

    python scripts/validate_skills.py                  # 校验本目录的 .agents/skills
    python scripts/validate_skills.py --root <路径>     # 校验指定项目根
    python scripts/validate_skills.py --max-chars 20000

退出码：0 = 全部通过；1 = 存在错误项（警告不影响退出码）。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SKILLS_DIR = ".agents/skills"


def _read_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    """返回 (字段字典, 错误信息)。字段只取一级 key: value，够校验用。"""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        return {}, f"无法读取：{error}"

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, "第一行必须是 '---'（YAML frontmatter 起始）"

    body: list[str] = []
    closed = False
    for line in lines[1:]:
        if line.strip() in ("---", "..."):
            closed = True
            break
        body.append(line)
    if not closed:
        return {}, "frontmatter 未闭合：缺少结束的 '---'"

    fields: dict[str, str] = {}
    for line in body:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip("'\"")
    return fields, ""


def validate(root: Path, max_chars: int) -> int:
    directory = root / SKILLS_DIR
    errors: list[str] = []
    warnings: list[str] = []

    if not directory.is_dir():
        print(f"错误：未找到技能目录 {directory}")
        return 1

    seen: dict[str, Path] = {}
    children = sorted(path for path in directory.iterdir() if path.is_dir())
    if not children:
        print(f"提示：{directory} 下没有 Skill 目录")

    for child in children:
        skill_file = child / "SKILL.md"
        label = f"{SKILLS_DIR}/{child.name}"
        if not skill_file.is_file():
            errors.append(f"{label}：缺少 SKILL.md")
            continue

        fields, error = _read_frontmatter(skill_file)
        if error:
            errors.append(f"{label}：{error}")
            continue

        name = fields.get("name", "")
        description = fields.get("description", "")
        if not name:
            errors.append(f"{label}：frontmatter 缺少 name")
        if not description:
            errors.append(f"{label}：frontmatter 缺少 description")
        if name in seen:
            errors.append(f"{label}：name '{name}' 与 {seen[name]} 重复")
        else:
            seen[name] = child

        if name and not NAME_PATTERN.match(name):
            warnings.append(f"{label}：name '{name}' 不是小写连字符格式（运行时可加载，但不利于 createSkill 复用）")
        if name and name != child.name:
            warnings.append(f"{label}：name '{name}' 与目录名 '{child.name}' 不一致（不影响加载）")

        size = len(skill_file.read_text(encoding="utf-8-sig"))
        if max_chars > 0 and size > max_chars:
            warnings.append(f"{label}：SKILL.md 共 {size} 字符，超过单次读取上限 {max_chars}，loadSkill 会截断")

        for extra in ("references", "scripts"):
            pass  # 辅助目录按需存在，不做强制校验

        if not error and name and description:
            print(f"[ok]   {label}  name={name}  {size} 字符")

    for item in warnings:
        print(f"[warn] {item}")
    for item in errors:
        print(f"[error] {item}")

    print(f"\n共 {len(children)} 个 Skill：{len(children) - len(errors)} 通过，{len(errors)} 失败，{len(warnings)} 警告")
    return 0 if not errors else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 Skill 目录与 frontmatter 是否符合加载契约")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="项目根目录（默认本脚本上级目录）")
    parser.add_argument("--max-chars", type=int, default=20000, help="SKILL.md 单次读取上限，超过只告警")
    args = parser.parse_args()
    return validate(Path(args.root).resolve(), args.max_chars)


if __name__ == "__main__":
    sys.exit(main())
