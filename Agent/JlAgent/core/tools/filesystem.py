import shutil
from pathlib import Path

from .base import Tool

TEXT_EXTS = {
    ".txt", ".md", ".mmd", ".py", ".js", ".ts", ".json", ".xml", ".yaml",
    ".yml", ".ini", ".cfg", ".csv", ".log", ".html", ".css",
}
PROJECT_DIR = Path(__file__).resolve().parents[2]


def build_tools(workspace: Path) -> list[Tool]:
    root = workspace.resolve()

    def resolve(path: str | Path) -> Path:
        raw = Path(path).expanduser()
        target = (root / raw if not raw.is_absolute() else raw).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"路径超出工作区 {root}")
        return target

    def list_dir(path: str = "") -> str:
        target = resolve(path or ".")
        if not target.is_dir():
            return f"错误：目录不存在 {target}"
        entries = sorted(
            target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())
        )
        return "\n".join(
            f"{'目录' if item.is_dir() else '文件'}: {item.name}" for item in entries
        ) or "目录为空"

    def get_file_type(path: str) -> str:
        target = resolve(path)
        if not target.exists():
            return f"错误：路径不存在 {target}"
        if target.is_dir():
            return "目录"
        ext = target.suffix.lower()
        if ext in TEXT_EXTS:
            return f"纯文本文件 ({ext})"
        return f"文件 ({ext or '无扩展名'})"

    def read_file(path: str) -> str:
        target = resolve(path)
        if not target.is_file():
            return f"错误：文件不存在 {target}"
        if target.suffix.lower() not in TEXT_EXTS:
            return "错误：仅支持纯文本格式文件"
        return target.read_text(encoding="utf-8")

    def create_file(dir: str, name: str, content: str = "") -> str:
        target = resolve(Path(dir) / name)
        if not target.parent.is_dir():
            return f"错误：目录不存在 {target.parent}"
        if target.exists():
            return f"错误：文件已存在 {target}"
        target.write_text(content, encoding="utf-8")
        return f"已创建文件 {target}"

    def edit_file(path: str, content: str) -> str:
        target = resolve(path)
        if not target.is_file():
            return f"错误：文件不存在 {target}"
        if target.suffix.lower() not in TEXT_EXTS:
            return "错误：仅支持纯文本格式文件"
        target.write_text(content, encoding="utf-8")
        return f"已更新文件 {target}"

    def create_dir(path: str) -> str:
        target = resolve(path)
        if target.exists():
            return f"错误：路径已存在 {target}"
        target.mkdir(parents=True)
        return f"已创建目录 {target}"

    def remove_dir(path: str) -> str:
        target = resolve(path)
        if not target.is_dir():
            return f"错误：目录不存在 {target}"
        if target in (root, PROJECT_DIR):
            return "错误：禁止删除工作区或程序目录"
        shutil.rmtree(target)
        return f"已删除目录 {target}"

    def remove_file(path: str) -> str:
        target = resolve(path)
        if not target.is_file():
            return f"错误：文件不存在 {target}"
        target.unlink()
        return f"已删除文件 {target}"

    def rename(src: str, dst: str) -> str:
        source = resolve(src)
        target = resolve(dst)
        if not source.exists():
            return f"错误：源路径不存在 {source}"
        if target.exists():
            return f"错误：目标路径已存在 {target}"
        if source in (root, PROJECT_DIR):
            return "错误：禁止重命名工作区或程序目录"
        source.rename(target)
        return f"已重命名 {source} -> {target}"

    return [
        Tool(
            "listDir",
            "列出指定目录下所有文件和子目录",
            {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "目标目录路径，留空表示工作区根目录",
                    }
                },
            },
            list_dir,
        ),
        Tool(
            "getFileType",
            "获取指定文件的类型",
            {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "文件路径"}},
                "required": ["path"],
            },
            get_file_type,
        ),
        Tool(
            "readFile",
            "获取指定文件的内容，仅支持纯文本格式文件",
            {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "文件路径"}},
                "required": ["path"],
            },
            read_file,
        ),
        Tool(
            "createFile",
            "根据指定的目录和文件名创建新文件",
            {
                "type": "object",
                "properties": {
                    "dir": {"type": "string", "description": "目标目录路径"},
                    "name": {"type": "string", "description": "文件名"},
                    "content": {"type": "string", "description": "初始内容，默认为空"},
                },
                "required": ["dir", "name"],
            },
            create_file,
        ),
        Tool(
            "editFile",
            "编辑指定文件的内容，仅支持纯文本格式文件",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "新内容"},
                },
                "required": ["path", "content"],
            },
            edit_file,
        ),
        Tool(
            "createDir",
            "创建新目录",
            {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "目录路径"}},
                "required": ["path"],
            },
            create_dir,
        ),
        Tool(
            "removeDir",
            "删除目录，包括非空目录",
            {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "目录路径"}},
                "required": ["path"],
            },
            remove_dir,
        ),
        Tool(
            "removeFile",
            "删除文件",
            {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "文件路径"}},
                "required": ["path"],
            },
            remove_file,
        ),
        Tool(
            "rename",
            "重命名文件和目录",
            {
                "type": "object",
                "properties": {
                    "src": {"type": "string", "description": "源路径"},
                    "dst": {"type": "string", "description": "目标路径"},
                },
                "required": ["src", "dst"],
            },
            rename,
        ),
    ]
