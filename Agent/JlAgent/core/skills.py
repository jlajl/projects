from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    directory: Path


class SkillCatalog:
    def __init__(self, skills: list[Skill], project_root: Path):
        self.skills = skills
        self.project_root = project_root
        self._by_name = {skill.name: skill for skill in skills}

    def get(self, name: str) -> Skill | None:
        return self._by_name.get(name)

    @classmethod
    def discover(
        cls, project_root: Path, skills_dir: str = ".agents/skills"
    ) -> "SkillCatalog":
        relative = Path(skills_dir)
        root = _locate_skills_root(project_root.resolve(), relative)
        directory = root / relative
        skills: list[Skill] = []
        seen: set[str] = set()

        if directory.is_dir():
            for child in sorted(directory.iterdir()):
                if not child.is_dir():
                    continue
                metadata = _read_metadata(child / "SKILL.md")
                if metadata is None:
                    continue
                name, description = metadata
                if name in seen:
                    continue
                seen.add(name)
                skills.append(Skill(name, description, child.resolve()))

        return cls(skills, root)


def _locate_skills_root(start: Path, relative: Path) -> Path:
    current = start
    while True:
        if (current / relative).is_dir():
            return current
        if current.parent == current:
            return start
        current = current.parent


def _read_metadata(path: Path) -> tuple[str, str] | None:
    if not path.is_file():
        return None

    try:
        with path.open(encoding="utf-8-sig") as file:
            if file.readline().strip() != "---":
                return None
            lines = []
            for line in file:
                if line.strip() in ("---", "..."):
                    break
                lines.append(line)
            else:
                return None
    except (OSError, UnicodeDecodeError):
        return None

    try:
        data = yaml.safe_load("".join(lines))
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None

    name = data.get("name")
    description = data.get("description")
    if not isinstance(name, str) or not name.strip():
        return None
    if not isinstance(description, str) or not description.strip():
        return None
    return name.strip(), " ".join(description.split())


def build_system_prompt(base: str, catalog: SkillCatalog) -> str:
    if not catalog.skills:
        return base

    lines = ["你可以使用以下技能（Skills）："]
    for skill in catalog.skills:
        lines.append(f"- {skill.name}：{skill.description}")
    lines.append(
        "当用户的需求与某个技能的描述相符时，必须先调用 loadSkill 读取该技能的完整说明，"
        "再严格按照说明完成任务；技能内容引用其他文件时，可再用 filename 参数读取该文件。"
    )
    block = "\n".join(lines)
    return f"{base}\n\n{block}" if base else block
