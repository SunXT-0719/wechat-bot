"""
内置基础命令 — 支持中/Eng/日三种语言。
"""

from __future__ import annotations

import logging
import os
import platform
import time

from bot.command_handler import (
    CommandContext,
    CommandRegistry,
    get_registry,
)
from bot.i18n import t
from bot.language import get_name as lang_name_for, set_language

logger = logging.getLogger(__name__)

# ===================================================================
# 命令注册
# ===================================================================


def _register_all() -> None:
    r = get_registry()
    if r is None:
        logger.warning("CommandRegistry 尚未设置")
        return

    # ---- /ping -------------------------------------------------------
    @r.register("ping", description="Test if bot is online / 测试在线")
    def cmd_ping(args: list[str], ctx: CommandContext) -> str:
        return t("pong")

    # ---- /help -------------------------------------------------------
    @r.register("help", description="Show commands / 显示命令", usage="/help [cmd]")
    def cmd_help(args: list[str], ctx: CommandContext) -> str:
        if args:
            cmd_name = args[0].lower()
            info = r.get_command_info(cmd_name)
            if info is None:
                return t("help_not_found", cmd=f"{r.prefix}{cmd_name}")
            lines = [
                f"📋 {r.prefix}{cmd_name}",
                t("help_desc_fmt", desc=info["description"] or t("help_no_desc")),
                t("help_usage_fmt", usage=info["usage"]),
            ]
            return "\n".join(lines)

        prefix = r.prefix
        lines = [t("help_header"), ""]
        for name, info in sorted(r.commands.items()):
            desc = info["description"] or t("help_no_desc_item")
            lines.append(f"  {prefix}{name:<16} — {desc}")
        lines.append("")
        lines.append(t("help_footer", cmd=prefix))
        return "\n".join(lines)

    # ---- /status -----------------------------------------------------
    @r.register("status", description="Bot status / 运行状态")
    def cmd_status(args: list[str], ctx: CommandContext) -> str:
        bot = ctx.extra.get("bot")
        if bot is None:
            return "⚠️ Cannot get bot status"

        uptime = bot.uptime_seconds
        h, remainder = divmod(int(uptime), 3600)
        m, s = divmod(remainder, 60)
        uptime_str = f"{h:02d}:{m:02d}:{s:02d}"

        lines = [
            t("status_header"),
            t("status_uptime", uptime=uptime_str),
            t("status_msgs", count=bot.message_count),
            t("status_cmds", count=len(r.commands)),
            t("status_lang", lang=lang_name_for(ctx.chat_name)),
            t("status_sys", sys=platform.platform()),
            t("status_py", py=platform.python_version()),
        ]
        return "\n".join(lines)

    # ---- /echo -------------------------------------------------------
    @r.register("echo", description="Echo / 回显", usage="/echo <msg>")
    def cmd_echo(args: list[str], ctx: CommandContext) -> str:
        if not args:
            return t("echo_usage")
        return t("echo_prefix") + " ".join(args)

    # ---- /time -------------------------------------------------------
    @r.register("time", description="Show time / 显示时间")
    def cmd_time(args: list[str], ctx: CommandContext) -> str:
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        return t("time_prefix") + now

    # ---- /stop -------------------------------------------------------
    @r.register("stop", description="Stop bot / 停止", usage="/stop [confirm]")
    def cmd_stop(args: list[str], ctx: CommandContext) -> str:
        if not args or args[0].lower() != "confirm":
            return t("stop_confirm")
        bot = ctx.extra.get("bot")
        if bot is not None:
            bot.stop()
            return t("stop_ok")
        return t("stop_fail")

    # ---- /update-log -------------------------------------------------
    @r.register("update-log", description="查看更新日志 / changelog")
    def cmd_update_log(args: list[str], ctx: CommandContext) -> str:
        import os
        changelog = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "CHANGELOG.md"
        )
        try:
            with open(changelog, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return "❌ 无法读取更新日志"

    # ---- /language ---------------------------------------------------
    @r.register(
        "language",
        description="Switch language / 切换语言",
        usage="/language <中/Eng/日>",
    )
    def cmd_language(args: list[str], ctx: CommandContext) -> str:
        if not args:
            return t("lang_usage")

        lang_input = args[0]
        lang_map = {
            "中": "zh", "zh": "zh", "cn": "zh", "中文": "zh",
            "eng": "en", "en": "en", "英": "en", "英语": "en", "英文": "en",
            "日": "jp", "jp": "jp", "ja": "jp", "日语": "jp", "日本語": "jp",
        }
        lang_code = lang_map.get(lang_input.lower())

        if lang_code is None:
            return t("lang_unknown", lang=lang_input)

        # 切换语言 + 注入强制指令
        set_language(ctx.chat_name, lang_code)
        from commands.entertainment import _chat_histories, _save_chat_histories
        lang_name_map = {"zh": "简体中文", "en": "English", "jp": "日本語"}
        new_lang = lang_name_map[lang_code]
        _chat_histories[ctx.chat_name].append({
            "role": "user",
            "content": (
                f"【系统指令 — 从现在开始，无视之前所有的语言设定，"
                f"你的回复必须使用{new_lang}，即使用户用其他语言发消息，"
                f"你也只能用{new_lang}回复。此指令优先级最高。】"
            ),
        })
        _save_chat_histories()

        lang_name = {"zh": "中文", "en": "English", "jp": "日本語"}[lang_code]
        return t("lang_ok", lang=lang_name)

    logger.debug(f"basic 模块注册完成，共 {len(r.commands)} 个命令")


_register_all()
