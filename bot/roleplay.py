"""
角色扮演管理 — 套件模式。
- catalog: {name: prompt}  全局共享
- selections: {chat_id: name}  每个群聊选用哪一套
"""

from __future__ import annotations

import json
import os

_FILE = os.path.join(os.path.dirname(__file__), "..", ".roleplay.json")
_catalog: dict[str, str] = {}
_selections: dict[str, str] = {}


def get(chat_id: str) -> str:
    """返回当前群聊选中的角色提示词。无选中则返回空字符串。"""
    name = _selections.get(chat_id, "")
    if name and name in _catalog:
        return _catalog[name]
    return ""


def get_by_name(name: str) -> str | None:
    return _catalog.get(name)


def list_names() -> list[str]:
    return sorted(_catalog.keys())


def create(name: str, prompt: str) -> None:
    _catalog[name] = prompt
    _save()


def set_selection(chat_id: str, name: str) -> None:
    if name in _catalog:
        _selections[chat_id] = name
        _save()


def clear_selection(chat_id: str) -> None:
    _selections.pop(chat_id, None)
    _save()


def delete(name: str) -> bool:
    """Delete a roleplay from the catalog. Returns True if it existed."""
    if name not in _catalog:
        return False
    del _catalog[name]
    # Also clear any chat that was using this roleplay
    for chat_id, rp_name in list(_selections.items()):
        if rp_name == name:
            del _selections[chat_id]
    _save()
    return True


def get_selections() -> dict[str, str]:
    """Return a copy of {chat_id: roleplay_name}."""
    return dict(_selections)


def get_catalog() -> dict[str, str]:
    """Return a copy of the full roleplay catalog {name: prompt}."""
    return dict(_catalog)


def _save() -> None:
    try:
        with open(_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"catalog": _catalog, "selections": _selections},
                f, ensure_ascii=False, indent=2,
            )
    except Exception:
        pass


def load() -> None:
    global _catalog, _selections
    if os.path.exists(_FILE):
        try:
            with open(_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _catalog = data.get("catalog", {})
            _selections = data.get("selections", {})
        except Exception:
            _catalog = {}
            _selections = {}


load()
