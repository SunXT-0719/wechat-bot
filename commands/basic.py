"""
内置基础命令
-----------
这些命令在 bot 启动时通过 ``@register`` 装饰器自动注册，
无需手动导入——``discover_commands()`` 会扫描 ``commands/`` 包。

添加新命令：
    在本目录下新建任意 ``.py`` 文件，使用 ``get_registry().register(...)``
    装饰器即可，bot 会在下次启动时自动发现并加载。
"""

from __future__ import annotations

import logging
import platform
import time

from bot.command_handler import (
    CommandContext,
    CommandRegistry,
    get_registry,
)

logger = logging.getLogger(__name__)

# ===================================================================
# 命令注册（模块导入时自动执行）
# ===================================================================


def _register_all() -> None:
    """将所有命令注册到全局 registry。"""
    r = get_registry()
    if r is None:
        logger.warning(
            "CommandRegistry 尚未设置，basic 命令将不会注册。"
            "请确保 set_registry() 在 discover_commands() 之前被调用。"
        )
        return

    # ---- /ping -------------------------------------------------------
    @r.register("ping", description="测试机器人是否在线")
    def cmd_ping(args: list[str], ctx: CommandContext) -> str:
        """健康检查命令。"""
        return "🏓 pong!"

    # ---- /help -------------------------------------------------------
    @r.register("help", description="显示所有可用命令", usage="/help [命令名]")
    def cmd_help(args: list[str], ctx: CommandContext) -> str:
        """列出所有命令或显示某个命令的详细信息。"""
        if args:
            cmd_name = args[0].lower()
            info = r.get_command_info(cmd_name)
            if info is None:
                prefix = r.prefix
                return f"❓ 未找到命令: {prefix}{cmd_name}"
            lines = [
                f"📋 {r.prefix}{cmd_name}",
                f"   描述: {info['description'] or '(无)'}",
                f"   用法: {info['usage']}",
            ]
            return "\n".join(lines)

        prefix = r.prefix
        lines = ["📋 可用命令:", ""]
        for name, info in sorted(r.commands.items()):
            desc = info["description"] or "(无描述)"
            lines.append(f"  {prefix}{name:<16} — {desc}")
        lines.append("")
        lines.append(f"输入 {prefix}help <命令名> 查看命令详细用法")
        return "\n".join(lines)

    # ---- /status -----------------------------------------------------
    @r.register("status", description="查看机器人运行状态")
    def cmd_status(args: list[str], ctx: CommandContext) -> str:
        """显示机器人当前状态。"""
        bot = ctx.extra.get("bot")
        if bot is None:
            return "⚠️ 无法获取机器人状态（bot 引用不可用）"

        uptime = bot.uptime_seconds
        h, remainder = divmod(int(uptime), 3600)
        m, s = divmod(remainder, 60)
        uptime_str = f"{h:02d}:{m:02d}:{s:02d}"

        lines = [
            "📊 机器人状态",
            f"   运行时间: {uptime_str}",
            f"   处理消息: {bot.message_count} 条",
            f"   已注册命令: {len(r.commands)} 个",
            f"   系统: {platform.platform()}",
            f"   Python: {platform.python_version()}",
        ]
        return "\n".join(lines)

    # ---- /echo -------------------------------------------------------
    @r.register("echo", description="回显消息（用于测试）", usage="/echo <消息>")
    def cmd_echo(args: list[str], ctx: CommandContext) -> str:
        """原样返回参数内容。"""
        if not args:
            return "用法: /echo <消息内容>"
        return "🔊 " + " ".join(args)

    # ---- /time -------------------------------------------------------
    @r.register("time", description="显示当前时间")
    def cmd_time(args: list[str], ctx: CommandContext) -> str:
        """返回服务器当前时间。"""
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        return f"🕐 当前时间: {now}"

    # ---- /stop (仅用于开发调试) --------------------------------------
    @r.register("stop", description="停止机器人（需确认）", usage="/stop [confirm]")
    def cmd_stop(args: list[str], ctx: CommandContext) -> str:
        """带确认的停止命令。"""
        if not args or args[0].lower() != "confirm":
            return "⚠️ 确定要停止机器人吗？输入 /stop confirm 确认。"
        bot = ctx.extra.get("bot")
        if bot is not None:
            bot.stop()
            return "👋 机器人正在停止..."
        return "⚠️ 无法停止（bot 引用不可用）"

    # ---- /confirm-on ---------------------------------------------------
    @r.register("confirm-on", description="重新开启发送确认弹窗")
    def cmd_confirm_on(args: list[str], ctx: CommandContext) -> str:
        """删除静音标记文件，恢复发送前弹窗。"""
        import os

        mute_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), ".no_confirm"
        )
        if os.path.exists(mute_file):
            os.remove(mute_file)
            return "✅ 发送确认弹窗已重新开启"
        return "ℹ️ 发送确认弹窗本来就是开启的"

    logger.debug(f"basic 模块注册完成，共 {len(r.commands)} 个命令")


# 模块导入时自动执行注册
_register_all()
