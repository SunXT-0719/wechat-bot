"""
Command registry and dispatcher.

Commands are functions registered with a decorator::

    registry = CommandRegistry(prefix="/")

    @registry.register("ping", description="健康检查")
    def cmd_ping(args: list[str], ctx: CommandContext) -> str | None:
        return "pong!"

The framework auto-discovers command modules from the ``commands/``
package on startup.
"""

from __future__ import annotations

import logging
import shlex
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

# A command handler receives the argument list and a context object.
# It should return a reply string or None (no reply).
CommandFunc = Callable[..., str | None]

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class CommandContext:
    """Metadata passed to every command handler."""

    chat_name: str             # 聊天窗口名（群名 或 联系人昵称）
    sender: str                # 发送者昵称
    is_group: bool             # 是否是群聊消息
    bot_nicknames: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedCommand:
    """Result of parsing a message as a potential command."""

    name: str          # e.g. "ping"
    args: list[str]    # e.g. ["hello", "world"]
    raw_text: str      # original message text
    is_valid: bool     # True if the message looked like a command


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class CommandRegistry:
    """Collect, parse, and dispatch slash-commands."""

    def __init__(self, prefix: str = "/") -> None:
        self.prefix = prefix
        self._commands: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        *,
        description: str = "",
        usage: str = "",
    ):
        """Decorator that registers the decorated function as a command.

        Usage::

            @registry.register("ping", description="测试机器人是否在线")
            def handle_ping(args, ctx):
                return "pong!"
        """
        name = name.lower().lstrip(self.prefix)

        def decorator(func: CommandFunc) -> CommandFunc:
            self._commands[name] = {
                "func": func,
                "description": description,
                "usage": usage or f"{self.prefix}{name}",
            }
            logger.debug(f"已注册命令: {self.prefix}{name}")
            return func

        return decorator

    def register_command(
        self,
        name: str,
        func: CommandFunc,
        *,
        description: str = "",
        usage: str = "",
    ) -> None:
        """Programmatic alternative to the decorator."""
        name = name.lower().lstrip(self.prefix)
        self._commands[name] = {
            "func": func,
            "description": description,
            "usage": usage or f"{self.prefix}{name}",
        }
        logger.debug(f"已注册命令: {self.prefix}{name}")

    def unregister(self, name: str) -> bool:
        name = name.lower().lstrip(self.prefix)
        if name in self._commands:
            del self._commands[name]
            return True
        return False

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse(self, text: str) -> ParsedCommand | None:
        """Try to extract a command from raw message text.

        Returns ``None`` when the message does not look like a command.
        """
        text = text.strip()
        if not text.startswith(self.prefix):
            return None

        # 去掉前缀后按空白分割
        body = text[len(self.prefix):].strip()
        if not body:
            return None

        try:
            parts = shlex.split(body)
        except ValueError:
            # 引号不匹配时就按简单空白分割
            parts = body.split()

        if not parts:
            return None

        return ParsedCommand(
            name=parts[0].lower(),
            args=parts[1:],
            raw_text=text,
            is_valid=True,
        )

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(self, parsed: ParsedCommand, ctx: CommandContext) -> str | None:
        """Execute a parsed command and return its reply text (or None)."""
        cmd_name = parsed.name

        entry = self._commands.get(cmd_name)
        if entry is None:
            from bot.i18n import t, set_chat_context
            set_chat_context(ctx.chat_name)
            available = ", ".join(sorted(self._commands.keys())) or "(none)"
            return t("unknown_cmd", cmd=f"{self.prefix}{cmd_name}", cmds=available)

        try:
            result = entry["func"](parsed.args, ctx)
            return result
        except Exception:
            logger.exception(f"命令 {self.prefix}{cmd_name} 执行出错")
            from bot.i18n import t, set_chat_context
            set_chat_context(ctx.chat_name)
            return t("cmd_error", cmd=f"{self.prefix}{cmd_name}")

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def commands(self) -> dict[str, dict[str, Any]]:
        """Return a copy of the command registry."""
        return dict(self._commands)

    def get_command_info(self, name: str) -> dict[str, Any] | None:
        return self._commands.get(name.lower().lstrip(self.prefix))


# ---------------------------------------------------------------------------
# Auto-discovery of command modules
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Global registry reference (for command modules to use at import time)
# ---------------------------------------------------------------------------

_global_registry: CommandRegistry | None = None


def set_registry(registry: CommandRegistry) -> None:
    """Set the global CommandRegistry instance.

    Called by bot_core BEFORE discover_commands() so that command
    modules can access the registry at import time via get_registry().
    """
    global _global_registry
    _global_registry = registry


def get_registry() -> CommandRegistry | None:
    """Return the global CommandRegistry, or None if not yet set."""
    return _global_registry


def discover_commands(
    registry: CommandRegistry,
    package_name: str = "commands",
) -> int:
    """Import ``commands.*`` modules so their ``@register`` decorators fire.

    Returns the number of modules successfully loaded.
    """
    import importlib
    import pkgutil

    count = 0
    try:
        package = importlib.import_module(package_name)
    except ImportError:
        logger.warning(f"无法导入命令包: {package_name}")
        return 0

    for _, mod_name, is_pkg in pkgutil.iter_modules(
        package.__path__, package.__name__ + "."
    ):
        if is_pkg:
            continue
        try:
            importlib.import_module(mod_name)
            count += 1
        except Exception:
            logger.exception(f"加载命令模块失败: {mod_name}")

    logger.info(f"从 {package_name!r} 包加载了 {count} 个命令模块")
    return count
