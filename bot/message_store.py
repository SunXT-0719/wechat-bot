"""
Per-chat message ring buffer with JSON-file persistence.

Survives bot restarts — messages are flushed to disk on every write.
"""

from __future__ import annotations

import json
import os
import threading
from collections import deque
from typing import NamedTuple


class StoredMessage(NamedTuple):
    sender: str
    content: str

    def format(self) -> str:
        return f"{self.sender}: {self.content}"

    def to_dict(self) -> dict:
        return {"sender": self.sender, "content": self.content}

    @classmethod
    def from_dict(cls, d: dict) -> "StoredMessage":
        return cls(sender=d["sender"], content=d["content"])


class MessageStore:
    """Thread-safe ring buffer per chat, persisted to a JSONL file."""

    def __init__(self, file_path: str = "", max_per_chat: int = 200) -> None:
        self._max = max_per_chat
        self._file = file_path
        self._lock = threading.Lock()
        self._buffers: dict[str, deque[StoredMessage]] = {}

        if self._file:
            self._load()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add(self, chat_name: str, sender: str, content: str) -> None:
        """Append one message and persist to disk."""
        msg = StoredMessage(sender=sender, content=content)
        with self._lock:
            buf = self._buffers.setdefault(
                chat_name, deque(maxlen=self._max)
            )
            buf.append(msg)
            self._save_one(chat_name, sender, content)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_recent(
        self, chat_name: str, count: int = 10, *, skip_last: int = 1
    ) -> list[StoredMessage]:
        with self._lock:
            buf = self._buffers.get(chat_name)
            if not buf:
                return []
            end = len(buf) - skip_last
            start = max(0, end - count)
            return list(buf)[start:end]

    def get_range(
        self, chat_name: str, k: int, m: int
    ) -> list[StoredMessage]:
        with self._lock:
            buf = self._buffers.get(chat_name)
            if not buf:
                return []
            total = len(buf)
            start = max(0, total - k)
            end = total - m + 1
            if end <= start:
                return []
            return list(buf)[start:end]

    # ------------------------------------------------------------------
    # Persistence (JSON Lines)
    # ------------------------------------------------------------------

    def _save_one(self, chat_name: str, sender: str, content: str) -> None:
        if not self._file:
            return
        try:
            line = json.dumps(
                {"chat": chat_name, "sender": sender, "content": content},
                ensure_ascii=False,
            )
            with open(self._file, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception:
            pass  # disk full or permission error — not critical

    def _load(self) -> None:
        if not self._file or not os.path.exists(self._file):
            return
        try:
            with open(self._file, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    chat = obj.get("chat", "")
                    sender = obj.get("sender", "")
                    content = obj.get("content", "")
                    if chat and content:
                        msg = StoredMessage(sender=sender, content=content)
                        buf = self._buffers.setdefault(
                            chat, deque(maxlen=self._max)
                        )
                        buf.append(msg)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_store: MessageStore | None = None


def get_message_store() -> MessageStore:
    global _store
    if _store is None:
        base = os.path.dirname(os.path.dirname(__file__))
        _store = MessageStore(
            file_path=os.path.join(base, "message_history.jsonl"),
            max_per_chat=500,
        )
    return _store
