"""
WeChat desktop client — unified interface with multiple backends.

Backends
--------
- **wxauto** (``WxAutoClient``) — UI Automation for WeChat **3.9.x** only.
  Requires WeChat 3.9.x desktop running and logged in.

- **WeFlow + pyautogui** (``WeFlowClient``) — works with **any** WeChat
  version. Uses WeFlow (https://weflow.top) for receiving messages via SSE
  and pyautogui for sending via GUI automation.

Use ``create_wechat_client(config)`` to instantiate the correct backend.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import pyperclip

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Message:
    """A single incoming WeChat message, normalised from wxauto's raw dict."""

    chat_name: str          # display name of the chat (group or contact)
    sender: str             # display name of the sender
    content: str            # cleaned message text
    msg_type: str           # "friend" | "group" | "sys" | "self"
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def is_group(self) -> bool:
        return self.msg_type == "group"

    @property
    def is_private(self) -> bool:
        return self.msg_type == "friend"

    @classmethod
    def from_wxauto(cls, chat_name: str, raw_msg: dict[str, Any]) -> "Message":
        """Factory: normalise one raw wxauto message dict."""
        sender = raw_msg.get("sender", "")
        content = raw_msg.get("content", "").strip()
        msg_type = raw_msg.get("type", "friend")

        return cls(
            chat_name=chat_name,
            sender=sender,
            content=content,
            msg_type=msg_type,
            raw=dict(raw_msg),
        )


# ---------------------------------------------------------------------------
# WeChat client
# ---------------------------------------------------------------------------


class WxAutoClient:
    """wxauto backend — only compatible with WeChat **3.9.x**.

    Drives the WeChat desktop client through Windows UI Automation (UIA).
    WeChat must be **running and logged in** on the same machine.

    Responsibilities
    ----------------
    - Read new messages (``poll_messages``)
    - Send text replies (``send_message``)
    - List recent sessions (``session_list``)
    """

    def __init__(self) -> None:
        self._wx: Any = None          # wxauto.WeChat instance (lazy init)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def wx(self) -> Any:
        """Lazy-init the wxauto WeChat object."""
        if self._wx is None:
            import wxauto as _  # type: ignore[import-untyped]

            self._wx = _.WeChat()
            logger.info("wxauto 已连接到微信客户端")
        return self._wx

    @property
    def ready(self) -> bool:
        return self._wx is not None

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def poll_messages(self) -> list[Message]:
        """Poll WeChat for new unread messages.

        Returns
        -------
        list[Message]
            Normalised messages since the last call (may be empty).
        """
        try:
            raw = self.wx.GetAllNewMessage()
        except Exception:
            logger.exception("GetAllNewMessage 失败")
            return []

        if not raw:
            return []

        messages: list[Message] = []
        for chat_name, msg_list in raw.items():
            # wxauto 有时把 chat_name 置为 ''
            if not chat_name:
                continue

            for raw_msg in msg_list:
                msg = Message.from_wxauto(str(chat_name), raw_msg)
                # 跳过系统消息和机器人自己的消息
                if msg.msg_type in ("sys", "self"):
                    continue
                if not msg.content:
                    continue
                messages.append(msg)

        return messages

    def get_session_list(self) -> list[str]:
        """Return the list of recent WeChat chat-session names."""
        try:
            return list(self.wx.GetSessionList())
        except Exception:
            logger.exception("GetSessionList 失败")
            return []

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    def send_message(self, chat_name: str, text: str) -> bool:
        """Send **text** to a chat (group or private contact).

        Uses the clipboard + keyboard-simulation approach that is known
        to work with WeChat's DirectUI edit control.
        """
        if not text or not chat_name:
            return False

        try:
            # 1. 导航到目标聊天
            self.wx.ChatWith(chat_name)
            time.sleep(0.3)

            # 2. 将文本写入剪贴板
            pyperclip.copy(text)
            time.sleep(0.05)

            # 3. 定位编辑框（WeChat DirectUI 的 Edit 控件）
            edit_box = self._find_edit_box()
            if edit_box is None:
                logger.error(f"无法定位编辑框 -> 消息发送失败 (chat={chat_name!r})")
                return False

            # 4. 点击聚焦 → 粘贴 → 回车发送
            edit_box.Click()
            time.sleep(0.05)
            edit_box.SendKeys("{Ctrl}v")
            time.sleep(0.05)
            edit_box.SendKeys("{Enter}")

            preview = text[:60].replace("\n", "\\n")
            logger.info(f"已发送消息 -> {chat_name!r}: {preview}")
            return True

        except Exception:
            logger.exception(f"发送消息失败 (chat={chat_name!r})")
            return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _find_edit_box(self):
        """Locate the WeChat chat-input Edit control via UI Automation.

        WeChat uses Tencent DirectUI, so standard HWND-based approaches
        fail.  Instead we search the UIA tree for an EditControl with a
        reasonable search depth.
        """
        try:
            import uiautomation as auto  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("uiautomation 未安装，尝试使用 wxauto 内置方式发送")
            return None

        wechat_window = auto.WindowControl(
            searchDepth=1, ClassName="WeChatMainWndForPC"
        )
        if not wechat_window.Exists(maxSearchSeconds=1):
            logger.error("未找到微信主窗口 (WeChatMainWndForPC)")
            return None

        # 搜索深度 5 足够穿透 DirectUI 的容器层级
        edit_box = wechat_window.EditControl(searchDepth=10, ClassName="Edit")
        if not edit_box.Exists(maxSearchSeconds=1):
            logger.error("未找到微信输入框 (EditControl)")
            return None

        return edit_box


# Backward-compatible alias
WeChatClient = WxAutoClient


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_wechat_client(config) -> Any:
    """Create and return the appropriate WeChat client based on config.

    Parameters
    ----------
    config : BotConfig
        The bot configuration object.

    Returns
    -------
    WxAutoClient | WeFlowClient
        A client instance with ``poll_messages()``, ``send_message()``,
        and ``ready`` / ``start()`` / ``stop()`` methods.
    """
    backend = config.get("backend", "wxauto")
    logger.info(f"选择微信客户端后端: {backend}")

    if backend == "weflow":
        from bot.wechat_client_weflow import WeFlowClient

        client = WeFlowClient(
            base_url=config.weflow_base_url,
            access_token=config.weflow_access_token,
        )
        client.start()  # launch SSE listener thread
        return client
    else:
        # Default: wxauto
        client = WxAutoClient()
        return client
