"""
WeChatBot — the central orchestrator.

Ties together the WeChat client, command registry, and config into a
single polling loop that reads messages, routes them to command handlers,
and sends replies back.
"""

from __future__ import annotations

import logging
import signal
import time
from typing import Any

from bot.command_handler import (
    CommandContext,
    CommandRegistry,
    ParsedCommand,
    discover_commands,
)
from bot.config import BotConfig
from bot.message_store import get_message_store
from bot.wechat_client import Message, create_wechat_client

logger = logging.getLogger(__name__)


class WeChatBot:
    """Main bot application.

    Usage::

        bot = WeChatBot("config.json")
        bot.start()   # blocking call — runs until Ctrl+C
    """

    def __init__(self, config_path: str | None = None):
        # ---- config ---------------------------------------------------
        self.config = BotConfig(config_path)

        # ---- wechat client (factory selects backend from config) ------
        self.client = create_wechat_client(self.config)

        # ---- command registry ------------------------------------------
        self.commands = CommandRegistry(prefix=self.config.command_prefix)

        # ---- runtime state --------------------------------------------
        self._running = False
        self._start_time: float | None = None
        self._message_count: int = 0
        self._seen_msg_ids: set[tuple[str, str, str]] = set()  # dedup
        self._seen_max_size: int = 10_000  # prevent unbounded growth

        # ---- register built-in commands via auto-discovery -------------
        # IMPORTANT: set_registry() must be called BEFORE discover_commands()
        # so that command modules see the correct registry at import time.
        from bot.command_handler import set_registry
        set_registry(self.commands)
        discover_commands(self.commands, "commands")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the bot's main polling loop (blocking)."""
        self._running = True
        self._start_time = time.time()

        # 注册优雅退出
        signal.signal(signal.SIGINT, self._on_sigint)
        signal.signal(signal.SIGTERM, self._on_sigint)

        logger.info("=" * 50)
        logger.info("🤖 微信机器人启动")
        logger.info(f"   命令前缀: {self.config.command_prefix}")
        logger.info(f"   昵称: {self.config.bot_nicknames}")
        logger.info(f"   已注册命令: {len(self.commands.commands)} 个")
        logger.info("=" * 50)

        # 首次启动时发送 /clear 密钥给主人
        from commands.entertainment import deliver_initial_key
        deliver_initial_key(self)

        try:
            self._run_loop()
        except KeyboardInterrupt:
            logger.info("收到中断信号（KeyboardInterrupt）")
        finally:
            self._shutdown()

    def stop(self) -> None:
        """Signal the bot to stop (can be called from a command handler)."""
        self._running = False

    def reply(self, chat_name: str, text: str) -> bool:
        """Convenience wrapper — send a reply to a chat."""
        return self.client.send_message(chat_name, text)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def uptime_seconds(self) -> float:
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    @property
    def message_count(self) -> int:
        return self._message_count

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Poll WeChat for new messages and process each one."""
        poll_interval = self.config.poll_interval_seconds

        logger.info(
            f"开始轮询消息 (间隔 {poll_interval:.1f}s) — 按 Ctrl+C 停止"
        )

        while self._running:
            try:
                messages = self.client.poll_messages()
            except Exception:
                logger.exception("轮询消息时出错")
                time.sleep(poll_interval)
                continue

            for msg in messages:
                try:
                    self._process_message(msg)
                except Exception:
                    logger.exception(f"处理消息时出错: {msg!r}")

            # 每轮清一次去重集，允许下一轮处理相同内容的命令
            self._seen_msg_ids.clear()
            time.sleep(poll_interval)

    def _process_message(self, msg: Message) -> None:
        """Route a single incoming message."""
        # ---- 消息去重 -------------------------------------------------
        msg_key = (msg.chat_name, msg.sender, msg.content)
        if msg_key in self._seen_msg_ids:
            return
        self._seen_msg_ids.add(msg_key)
        # 防止 set 无限增长
        if len(self._seen_msg_ids) > self._seen_max_size:
            self._seen_msg_ids.clear()

        self._message_count += 1

        # ---- 存入消息历史（供 /笑点解析 等命令使用）--------------
        # 跳过 / 开头的命令消息
        if not msg.content.startswith("/"):
            get_message_store().add(msg.chat_name, msg.sender, msg.content)

        logger.debug(
            f"[{msg.msg_type}] {msg.chat_name!r} | "
            f"{msg.sender}: {msg.content[:80]}"
        )

        # ---- 群聊黑/白名单 ---------------------------------------------
        if msg.is_group:
            if not self._group_allowed(msg.chat_name):
                logger.debug(f"群 {msg.chat_name!r} 不在白名单/在黑名单中，跳过")
                return

        # ---- 预处理：去除 @机器人 提及 -----------------------------------
        # 支持 " @Bot /ping" 和 "/ping @Bot" 等格式
        clean_content = msg.content
        for nick in self.config.bot_nicknames:
            if nick:
                # 去除 @昵称 的各种变体 (含前后空格)
                clean_content = clean_content.replace(f"@{nick}", "")
                clean_content = clean_content.replace(f"@{nick} ", "")  # 微信 @ 后面有时跟半角空格
        clean_content = clean_content.strip()

        # ---- 尝试解析命令 ----------------------------------------------
        parsed = self.commands.parse(clean_content)

        if parsed and parsed.is_valid:
            # 群聊中: 检查是否需要 @机器人
            if msg.is_group and self.config.require_mention_for_commands:
                if not self._is_mentioned(msg.content):
                    return

            self._handle_command(msg, parsed)
            return

        # ---- @提及检测（用于未来 AI 对话扩展）------------------------
        if msg.is_group and self._is_mentioned(msg.content):
            logger.info(
                f"收到 @提及 (非命令): {msg.sender}: {msg.content[:80]}"
            )
            # TODO: 未来可在此接入 AI 对话
            return

        # ---- 私聊中的非命令消息 ----------------------------------------
        if msg.is_private:
            logger.info(
                f"收到私聊消息 (非命令): {msg.sender}: {msg.content[:80]}"
            )
            # TODO: 未来可在此接入 AI 对话
            return

    # ------------------------------------------------------------------
    # Command handling
    # ------------------------------------------------------------------

    def _handle_command(self, msg: Message, parsed: ParsedCommand) -> None:
        """Dispatch a parsed command and send back the reply."""
        ctx = CommandContext(
            chat_name=msg.chat_name,
            sender=msg.sender,
            is_group=msg.is_group,
            bot_nicknames=self.config.bot_nicknames,
            extra={"bot": self},
        )

        logger.info(
            f"执行命令 {self.config.command_prefix}{parsed.name} "
            f"来自 {msg.sender} (chat={msg.chat_name!r})"
        )

        reply_text = self.commands.dispatch(parsed, ctx)

        if reply_text is not None:
            self._confirm_and_send(msg.chat_name, str(reply_text))

    def _confirm_and_send(self, chat_name: str, text: str) -> None:
        """Run confirmation popup as subprocess, then send or pause."""
        import os
        import subprocess
        import sys

        # 如果已静音，直接发送
        mute_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), ".no_confirm"
        )
        if os.path.exists(mute_file):
            logger.info(f"[确认-步骤A] 已静音，直接发送 -> {chat_name!r}")
            self.client.send_message(chat_name, text)
            get_message_store().add(chat_name, "bot", text)
            return

        script = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "bot", "send_confirm.py",
        )

        logger.info(f"[确认-步骤B] 启动弹窗子进程 -> {chat_name!r}")
        logger.info(f"[确认-步骤B] 脚本: {script}")

        # 只传群名，不传文本（避免特殊字符破坏命令行参数）
        try:
            proc = subprocess.run(
                [sys.executable, script, chat_name],
                capture_output=True, text=True, timeout=600,
                creationflags=subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32" else 0,
            )
            result = proc.stdout.strip()
            logger.info(
                f"[确认-步骤C] 子进程返回: stdout={result!r} "
                f"stderr={proc.stderr[:200] if proc.stderr else ''!r} "
                f"rc={proc.returncode}"
            )
        except subprocess.TimeoutExpired:
            logger.error("[确认-步骤C] 子进程超时！")
            result = "send"
        except Exception:
            logger.exception("[确认-步骤C] 子进程异常")
            result = "send"

        if result == "mute":
            open(mute_file, "w").close()
            logger.info("[确认-步骤D] 用户关闭确认，发送")
        elif result == "pause":
            logger.info("[确认-步骤D] 用户挂起，直接发送")
        else:
            logger.info(f"[确认-步骤D] 发送 (result={result!r})")

        self.client.send_message(chat_name, text)
        # 将 bot 的回复也存入消息历史（笑点解析需要）
        get_message_store().add(chat_name, "bot", text)
        logger.info(f"[确认-步骤E] send_message 调用完成 -> {chat_name!r}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _group_allowed(self, group_name: str) -> bool:
        """Check white/blacklist for a group name."""
        whitelist = self.config.groups_whitelist
        blacklist = self.config.groups_blacklist

        if blacklist and group_name in blacklist:
            return False
        if whitelist and group_name not in whitelist:
            return False
        return True

    def _is_mentioned(self, content: str) -> bool:
        """Return True if any bot nickname appears in the message text."""
        for nick in self.config.bot_nicknames:
            if nick and nick in content:
                return True
        return False

    def _on_sigint(self, signum: int, frame: Any) -> None:
        logger.info(f"收到信号 {signum}，正在停止机器人...")
        self._running = False

    def _shutdown(self) -> None:
        logger.info(
            f"🤖 机器人已停止 — "
            f"运行时间 {self.uptime_seconds:.0f}s, "
            f"处理消息 {self._message_count} 条"
        )
