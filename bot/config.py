"""
Bot configuration management.
Loads settings from config.json with sensible defaults.
"""

import json
import os
from typing import Any


class BotConfig:
    """Typed wrapper around the bot's JSON configuration file."""

    # Path to the config file, relative to this module.
    DEFAULT_CONFIG_PATH = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config.json"
    )

    def __init__(self, config_path: str | None = None):
        self._path = config_path or self.DEFAULT_CONFIG_PATH
        self._data: dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Read (or re-read) the JSON config file on disk."""
        if not os.path.exists(self._path):
            raise FileNotFoundError(f"配置文件未找到: {self._path}")

        with open(self._path, "r", encoding="utf-8") as fh:
            self._data = json.load(fh)

    def reload(self) -> None:
        """Public helper to re-read config at runtime."""
        self._load()

    def save(self) -> None:
        """Write current in-memory config back to disk."""
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=4)

    # ------------------------------------------------------------------
    # Typed accessors (add new ones here as the config schema grows)
    # ------------------------------------------------------------------

    @property
    def bot_nicknames(self) -> list[str]:
        return self._data.get("bot_nicknames", ["机器人"])

    @property
    def command_prefix(self) -> str:
        return self._data.get("command_prefix", "/")

    @property
    def poll_interval_seconds(self) -> int | float:
        return self._data.get("poll_interval_seconds", 2)

    @property
    def debug(self) -> bool:
        return self._data.get("debug", False)

    @property
    def groups_whitelist(self) -> list[str]:
        """If non-empty, only these group names are served."""
        return self._data.get("groups_whitelist", [])

    @property
    def groups_blacklist(self) -> list[str]:
        """Group names that are explicitly ignored."""
        return self._data.get("groups_blacklist", [])

    @property
    def respond_to_all_commands_in_groups(self) -> bool:
        """When True, any /command in a group triggers the bot (not just @mentions)."""
        return self._data.get("respond_to_all_commands_in_groups", True)

    @property
    def require_mention_for_commands(self) -> bool:
        """When True, even /commands must @-mention the bot in groups."""
        return self._data.get("require_mention_for_commands", False)

    @property
    def log_file(self) -> str:
        return self._data.get("log_file", "bot.log")

    @property
    def log_level(self) -> str:
        return self._data.get("log_level", "INFO")

    @property
    def backend(self) -> str:
        """Which backend to use: 'wxauto' or 'weflow'."""
        return self._data.get("backend", "wxauto")

    @property
    def weflow_base_url(self) -> str:
        return self._data.get("weflow_base_url", "http://127.0.0.1:5031")

    @property
    def weflow_access_token(self) -> str:
        return self._data.get("weflow_access_token", "")

    # ------------------------------------------------------------------
    # Generic access (for custom plugins / future fields)
    # ------------------------------------------------------------------

    @property
    def deepseek_api_key(self) -> str:
        return self._data.get("deepseek_api_key", "")

    @property
    def deepseek_model(self) -> str:
        return self._data.get("deepseek_model", "deepseek-chat")

    @property
    def deepseek_base_url(self) -> str:
        return self._data.get("deepseek_base_url", "https://api.deepseek.com/v1/chat/completions")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __repr__(self) -> str:
        return f"<BotConfig path={self._path!r}>"
