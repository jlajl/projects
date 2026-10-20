import configparser, os, subprocess, shutil, json
from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

config = configparser.ConfigParser()
config.read(os.path.join(BASE_DIR, "config.ini"), encoding="utf-8")
llm = config["llm"]

client = OpenAI(api_key=llm["api_key"], base_url=llm["base_url"])

tools = [
    {
        "type": "function",
        "function": {
            "name": "getDate",
            "description": "获取当前电脑的日期和时间",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "getCwd",
            "description": "获取当前工作目录",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listDir",
            "description": "列出指定目录下所有文件和子目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目标目录路径，留空表示当前目录"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "getFileType",
            "description": "获取指定文件的类型",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "文件路径"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "readFile",
            "description": "获取指定文件的内容，仅支持纯文本格式文件",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "文件路径"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "createFile",
            "description": "根据指定的目录和文件名创建新文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir": {"type": "string", "description": "目标目录路径"},
                    "name": {"type": "string", "description": "文件名"},
                    "content": {"type": "string", "description": "初始内容，默认为空"},
                },
                "required": ["dir", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "editFile",
            "description": "编辑指定文件的内容，仅支持纯文本格式文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "新内容"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "createDir",
            "description": "创建新目录",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "目录路径"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "removeDir",
            "description": "删除目录，包括非空目录",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "目录路径"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "removeFile",
            "description": "删除文件",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "文件路径"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rename",
            "description": "重命名文件和目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {"type": "string", "description": "源路径"},
                    "dst": {"type": "string", "description": "目标路径"},
                },
                "required": ["src", "dst"],
            },
        },
    },
]

def getDate():
    return subprocess.run(
        "date /t & time /t", shell=True, capture_output=True, text=True
    ).stdout.strip()

def getCwd():
    return os.getcwd()

def listDir(path=""):
    p = path or "."
    if not os.path.isdir(p):
        return f"错误：目录不存在 {p}"
    entries = []
    for name in os.listdir(p):
        full = os.path.join(p, name)
        tag = "目录" if os.path.isdir(full) else "文件"
        entries.append(f"{tag}: {name}")
    return "\n".join(entries) if entries else "目录为空"

TEXT_EXTS = {".txt", ".md", ".mmd", ".py", ".js", ".ts", ".json", ".xml", ".yaml",
             ".yml", ".ini", ".cfg", ".csv", ".log", ".html", ".css"}

def getFileType(path):
    if not os.path.exists(path):
        return f"错误：路径不存在 {path}"
    if os.path.isdir(path):
        return "目录"
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_EXTS:
        return f"纯文本文件 ({ext})"
    return f"文件 ({ext or '无扩展名'})"

def readFile(path):
    if not os.path.isfile(path):
        return f"错误：文件不存在 {path}"
    if os.path.splitext(path)[1].lower() not in TEXT_EXTS:
        return "错误：仅支持纯文本格式文件"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def createFile(dir, name, content=""):
    if not os.path.isdir(dir):
        return f"错误：目录不存在 {dir}"
    path = os.path.join(dir, name)
    if os.path.exists(path):
        return f"错误：文件已存在 {path}"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"已创建文件 {path}"

def editFile(path, content):
    if not os.path.isfile(path):
        return f"错误：文件不存在 {path}"
    if os.path.splitext(path)[1].lower() not in TEXT_EXTS:
        return "错误：仅支持纯文本格式文件"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"已更新文件 {path}"

def createDir(path):
    if os.path.exists(path):
        return f"错误：路径已存在 {path}"
    os.makedirs(path)
    return f"已创建目录 {path}"

def _is_forbidden(path):
    p = os.path.abspath(path)
    return p == BASE_DIR or p == os.path.abspath(os.getcwd())

def removeDir(path):
    if not os.path.isdir(path):
        return f"错误：目录不存在 {path}"
    if _is_forbidden(path):
        return "错误：禁止删除程序所在目录或当前工作目录"
    shutil.rmtree(path)
    return f"已删除目录 {path}"

def removeFile(path):
    if not os.path.isfile(path):
        return f"错误：文件不存在 {path}"
    if os.path.abspath(path) == os.path.abspath(__file__):
        return "错误：禁止删除程序自身"
    os.remove(path)
    return f"已删除文件 {path}"

def rename(src, dst):
    if not os.path.exists(src):
        return f"错误：源路径不存在 {src}"
    if os.path.exists(dst):
        return f"错误：目标路径已存在 {dst}"
    if _is_forbidden(src):
        return "错误：禁止重命名程序所在目录或当前工作目录"
    os.rename(src, dst)
    return f"已重命名 {src} -> {dst}"

dispatch = {
    "getDate": getDate,
    "getCwd": getCwd,
    "listDir": listDir,
    "getFileType": getFileType,
    "readFile": readFile,
    "createFile": createFile,
    "editFile": editFile,
    "createDir": createDir,
    "removeDir": removeDir,
    "removeFile": removeFile,
    "rename": rename,
}

messages = []
while True:
    messages.append({"role": "user", "content": input("请输入提示词: ")})
    while True:
        msg = client.chat.completions.create(
            model=llm["model_name"], messages=messages, tools=tools
        ).choices[0].message
        messages.append(msg)
        if not msg.tool_calls:
            print(msg.content)
            break
        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
                result = dispatch[call.function.name](**args)
            except Exception as e:
                result = f"工具执行失败: {e}"
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
