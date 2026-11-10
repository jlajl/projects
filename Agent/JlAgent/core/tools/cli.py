import locale
import subprocess

from .base import Tool


def _decode(data: bytes) -> str:
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode(locale.getpreferredencoding(False), errors="replace")


def _truncate(text: str, label: str, max_stream_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_stream_chars:
        return text
    return f"{text[:max_stream_chars]}\n…（{label} 已截断，共 {len(text)} 字符）"


def _format_streams(stdout: str, stderr: str, max_stream_chars: int) -> str:
    stdout = _truncate(stdout, "标准输出", max_stream_chars)
    stderr = _truncate(stderr, "标准错误", max_stream_chars)
    return f"标准输出：\n{stdout or '(空)'}\n\n标准错误：\n{stderr or '(空)'}"


def build_tools(
    workspace, exec_timeout: int = 30, max_stream_chars: int = 4000
) -> list[Tool]:
    def run_cli(command: str, args: list[str] | None = None) -> str:
        command = command.strip()
        if not command:
            return "错误：程序名称不能为空"
        if args is None:
            args = []
        if not isinstance(args, list):
            return "错误：参数 args 必须是字符串列表"

        argv = [command, *(str(arg) for arg in args)]
        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                timeout=exec_timeout,
                cwd=workspace,
            )
        except FileNotFoundError:
            return f"错误：找不到命令 {command}，请确认程序已安装并在 PATH 中"
        except PermissionError:
            return f"错误：没有权限执行 {command}"
        except subprocess.TimeoutExpired as error:
            streams = _format_streams(
                _decode(error.stdout or b""),
                _decode(error.stderr or b""),
                max_stream_chars,
            )
            return (
                f"错误：命令执行超时（{exec_timeout} 秒），进程已被终止\n\n{streams}"
            )
        except ValueError as error:
            return f"错误：命令参数无效：{error}"
        except OSError as error:
            return f"错误：无法执行 {command}：{error}"

        streams = _format_streams(
            _decode(completed.stdout), _decode(completed.stderr), max_stream_chars
        )
        return f"退出码：{completed.returncode}\n\n{streams}"

    return [
        Tool(
            "RunCLI",
            "以当前用户权限执行本地命令行程序，返回退出码、标准输出和标准错误。"
            "仅支持可执行程序（如 git、python、curl），无法执行 dir、cd 等 Shell 内置命令。",
            {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "程序名称，例如 git、python、curl",
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "传给程序的参数列表，不包含程序名称本身",
                    },
                },
                "required": ["command"],
            },
            run_cli,
        )
    ]
