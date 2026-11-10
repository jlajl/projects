"""会话持久化：把对话历史保存到 ``.agents/sessions/``，支持列表与恢复。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .agent import AGENTS_MD_NAME

SESSION_SUFFIX = ".json"


@dataclass(frozen=True)
class SessionSummary:
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


def _make_title(messages: list[dict], limit: int = 40) -> str:
    for message in messages:
        if message.get("role") != "user":
            continue
        if message.get("name") == AGENTS_MD_NAME:
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            text = " ".join(content.split())
            return text[:limit] + ("…" if len(text) > limit else "")
    return ""


class SessionStore:
    """把会话以 JSON 文件形式持久化，文件名即会话编号。"""

    def __init__(self, workspace: Path):
        self.dir = workspace / ".agents" / "sessions"

    def new_id(self) -> str:
        return datetime.now().strftime("%Y%m%d-%H%M%S-%f")

    def _path(self, session_id: str) -> Path:
        return self.dir / f"{session_id}{SESSION_SUFFIX}"

    def save(
        self,
        session_id: str,
        messages: list[dict],
        title: str | None = None,
    ) -> SessionSummary:
        self.dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        now_str = now.isoformat(timespec="seconds")
        created_at = now_str

        path = self._path(session_id)
        if path.is_file():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                created_at = existing.get("created_at", now_str)
            except (OSError, json.JSONDecodeError):
                pass

        data = {
            "id": session_id,
            "title": title or _make_title(messages) or session_id,
            "created_at": created_at,
            "updated_at": now_str,
            "messages": [dict(message) for message in messages],
        }
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return SessionSummary(
            session_id, data["title"], created_at, now_str, len(messages)
        )

    def load(self, session_id: str) -> list[dict]:
        path = self._path(session_id)
        if not path.is_file():
            raise FileNotFoundError(f"会话不存在：{session_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data.get("messages", []))

    def list_sessions(self) -> list[SessionSummary]:
        if not self.dir.is_dir():
            return []
        result: list[SessionSummary] = []
        for path in self.dir.glob(f"*{SESSION_SUFFIX}"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            result.append(
                SessionSummary(
                    id=data.get("id", path.stem),
                    title=data.get("title", path.stem),
                    created_at=data.get("created_at", ""),
                    updated_at=data.get("updated_at", ""),
                    message_count=len(data.get("messages", [])),
                )
            )
        result.sort(key=lambda item: item.updated_at, reverse=True)
        return result