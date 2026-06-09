"""
语言模式管理 — 按群聊隔离，持久化到 .language.json。
"""

from __future__ import annotations

import json
import os

_FILE = os.path.join(os.path.dirname(__file__), "..", ".language.json")
_DATA: dict[str, str] = {}
_DEFAULT = "zh"


def get(chat_id: str = "") -> str:
    """返回指定群聊的语言: 'zh' | 'en' | 'jp'. 无设置则默认中文。"""
    return _DATA.get(chat_id, _DEFAULT)


def set_language(chat_id: str, lang: str) -> None:
    """设置指定群聊的语言并保存。"""
    _DATA[chat_id] = lang
    _save()


def get_name(chat_id: str = "") -> str:
    return {"zh": "中文", "en": "English", "jp": "日本語"}.get(get(chat_id), "中文")


def lang_prompt_instr(chat_id: str = "") -> str:
    mapping = {
        "zh": (
            "你的回复必须使用简体中文。"
            "即使用户用其他语言发消息，你也只能用中文回复，绝对不能使用其他语言。"
        ),
        "en": (
            "You MUST reply in English only, regardless of what language "
            "the user uses. Never use Chinese, Japanese, or any other language."
        ),
        "jp": (
            "返信は必ず日本語で行ってください。"
            "ユーザーが他の言語でメッセージを送っても、日本語のみで返信し、"
            "他の言語を絶対に使用しないでください。"
        ),
    }
    return mapping.get(get(chat_id), "")


def _save() -> None:
    try:
        with open(_FILE, "w", encoding="utf-8") as f:
            json.dump(_DATA, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load() -> None:
    global _DATA
    if os.path.exists(_FILE):
        try:
            with open(_FILE, "r", encoding="utf-8") as f:
                _DATA = json.load(f)
        except Exception:
            _DATA = {}


load()
