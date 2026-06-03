"""
WeFlow + pyautogui WeChat client backend.

**Unlike wxauto, this works with ANY WeChat version** because it uses:

- **WeFlow** (https://weflow.top) — a local tool that reads WeChat's message
  database and pushes new messages via Server-Sent Events (SSE).
  Runs at ``http://127.0.0.1:5031``.

- **pyautogui** — GUI automation (keyboard/mouse simulation) to send
  replies through the visible WeChat window.

Prerequisites
-------------
1. Download and run WeFlow from https://weflow.top
2. In WeFlow settings: enable "API 服务" + "主动推送" (API service + push)
3. Copy the Access Token from WeFlow into config.json
4. WeChat desktop must be running, logged in, and visible (not minimized)
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from typing import Any

import pyperclip
import requests

from bot.wechat_client import Message

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Message type codes from WeFlow that we should ignore
IGNORE_MSG_TYPES = {34, 47}  # 34 = voice, 47 = sticker/emoji

# Text placeholders that indicate non-text messages
IGNORE_CONTENT_MARKERS = ["[语音]", "[表情]", "[图片]", "[视频]", "[文件]"]


class WeFlowClient:
    """WeChat client that reads via WeFlow SSE and sends via pyautogui.

    Implements the same interface as ``WeChatClient`` (wxauto) so the
    bot core can use either backend transparently.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:5031",
        access_token: str = "",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token

        # ---- message queue (SSE thread → main loop) -----------------
        self._queue: queue.Queue[Message] = queue.Queue()

        # ---- dedup ---------------------------------------------------
        self._seen_ids: set[str] = set()
        self._seen_content: dict[tuple, float] = {}  # key → timestamp
        self._seen_max = 10_000

        # ---- SSE thread control -------------------------------------
        self._running = False
        self._thread: threading.Thread | None = None
        self._start_time = int(time.time())  # skip messages before this

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def ready(self) -> bool:
        return self._running

    def start(self) -> None:
        """Launch the SSE listener in a background daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_sse, daemon=True)
        self._thread.start()
        logger.info("WeFlow SSE 监听线程已启动")

    def stop(self) -> None:
        """Signal the SSE listener to stop."""
        self._running = False

    # ------------------------------------------------------------------
    # Read (called from bot main loop)
    # ------------------------------------------------------------------

    def poll_messages(self) -> list[Message]:
        """Drain all queued messages without blocking.

        Returns
        -------
        list[Message]
            Messages received since the last call (may be empty).
        """
        messages: list[Message] = []
        while True:
            try:
                msg = self._queue.get_nowait()
                messages.append(msg)
            except queue.Empty:
                break
        return messages

    def get_session_list(self) -> list[str]:
        """Session list is not available via WeFlow — returns empty list."""
        return []

    # ------------------------------------------------------------------
    # Send — win32 + pyautogui
    # ------------------------------------------------------------------

    def send_message(self, chat_name: str, text: str) -> bool:
        """Send text to *chat_name*.

        1. Activate WeChat via Win32 API.
        2. Ctrl+F search with a **cleaned** name (special chars
           stripped — avoids triggering web-search).
        3. Paste reply and Enter.
        """
        if not text or not chat_name:
            return False

        try:
            import pyautogui  # type: ignore[import-untyped]
        except ImportError:
            logger.error("pyautogui 未安装")
            return False

        try:
            # ---- 1. Win32 激活微信窗口 -------------------------------
            hwnd = self._find_wechat_hwnd()
            if hwnd is None:
                logger.error("未找到微信窗口，请确认微信已登录且可见")
                return False

            self._force_foreground(hwnd)
            time.sleep(0.3)

            # ---- 2. Ctrl+F 搜索 ------------------------------------
            logger.debug(f"Ctrl+F 搜索: {chat_name!r}")

            pyautogui.hotkey("ctrl", "f")
            time.sleep(0.3)
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.05)
            pyperclip.copy(chat_name)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.6)

            # 直接 Enter 打开第一个搜索结果（群聊已在首位）
            pyautogui.press("enter")
            time.sleep(1.0)

            # ---- 3. 粘贴发送（聊天打开后输入区自动获得焦点）---------
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.2)
            pyautogui.press("enter")

            preview = text[:60].replace("\n", "\\n")
            logger.info(f"已发送 -> {chat_name!r}: {preview}")
            return True

        except Exception:
            logger.exception(f"发送消息失败 (chat={chat_name!r})")
            return False

    # ------------------------------------------------------------------
    # Keyboard-level send helpers
    # ------------------------------------------------------------------

    def _keyboard_send(self, text: str) -> None:
        """Clear any existing input, paste *text*, and press Enter."""
        import pyautogui  # type: ignore[import-untyped]

        # WeChat 中打开聊天后输入区通常已有焦点，直接粘贴即可
        pyautogui.hotkey("ctrl", "a")   # 全选现有内容
        time.sleep(0.05)
        pyautogui.press("delete")       # 清空
        time.sleep(0.05)

        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")   # 粘贴
        time.sleep(0.2)

        pyautogui.press("enter")        # 发送
        time.sleep(0.1)

    # ------------------------------------------------------------------
    # SSE listener (background thread)
    # ------------------------------------------------------------------

    def _listen_sse(self) -> None:
        """Consume the WeFlow SSE push stream indefinitely."""
        url = (
            f"{self._base_url}/api/v1/push/messages"
            f"?access_token={self._access_token}"
        )
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        }

        logger.info(f"正在连接 WeFlow SSE: {self._base_url}")
        self._start_time = int(time.time())

        while self._running:
            try:
                response = requests.get(
                    url, headers=headers, stream=True, timeout=(10, None)
                )
                if response.status_code != 200:
                    logger.error(
                        f"WeFlow 连接失败 (HTTP {response.status_code})，"
                        f"5 秒后重试..."
                    )
                    time.sleep(5)
                    continue

                logger.info("✅ 已连接到 WeFlow 推送服务")

                for line in response.iter_lines(decode_unicode=True):
                    if not self._running:
                        break

                    if not line:
                        continue

                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                        if event_type == "message.revoke":
                            logger.debug("收到撤回消息通知")
                        continue

                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if not data_str:
                            continue
                        try:
                            self._handle_sse_data(json.loads(data_str))
                        except json.JSONDecodeError:
                            logger.debug(f"无法解析 SSE data: {data_str[:100]}")
                        except Exception:
                            logger.exception("处理 SSE 消息时出错")

            except requests.ConnectionError:
                logger.warning("WeFlow 连接断开，5 秒后重试...")
                time.sleep(5)
            except Exception:
                logger.exception("SSE 监听异常，5 秒后重试...")
                time.sleep(5)

        logger.info("SSE 监听线程已退出")

    def _handle_sse_data(self, data: dict[str, Any]) -> None:
        """Parse one WeFlow SSE ``data:`` payload into a Message and enqueue it."""
        # ---- 时间过滤：跳过启动前的历史消息 --------------------------
        timestamp = data.get("timestamp", 0)
        if isinstance(timestamp, (int, float)) and timestamp < self._start_time:
            return

        # ---- 去重 ----------------------------------------------------
        raw_id = data.get("rawid", "")
        content_raw = data.get("content", "").strip()

        # 1) rawid 去重（永久）
        if raw_id and raw_id in self._seen_ids:
            return
        if raw_id:
            self._seen_ids.add(raw_id)

        # 2) 内容去重（5秒窗口，超时后相同内容可以再次触发）
        content_key = (
            data.get("sourceName", ""),
            data.get("groupName", ""),
            content_raw,
        )
        now = time.time()
        if content_raw and content_key in self._seen_content:
            last_time = self._seen_content[content_key]
            if now - last_time < 5.0:
                return
        if content_raw:
            self._seen_content[content_key] = now

        # 防止 dict 无限增长
        if len(self._seen_content) > self._seen_max:
            self._seen_content.clear()
        if len(self._seen_ids) > self._seen_max:
            self._seen_ids.clear()

        # ---- 首次收到消息时输出完整原始数据，帮助调试字段结构 ---------
        if raw_id and len(self._seen_ids) <= 5:
            logger.info(
                f"WeFlow 原始数据 #{len(self._seen_ids)}: "
                f"{json.dumps(data, ensure_ascii=False)[:500]}"
            )

        # ---- 消息类型过滤 -------------------------------------------
        msg_type = data.get("type", 0) or data.get("msgType", 0)
        if msg_type in IGNORE_MSG_TYPES:
            return

        if not content_raw:
            return
        # 过滤 [语音]、[表情] 等占位文本
        if any(marker in content_raw for marker in IGNORE_CONTENT_MARKERS):
            return

        # ---- 解析发送者和聊天名 -------------------------------------
        # WeFlow 实际字段结构（从实际数据验证）:
        #   私聊: sessionType="private", sourceName=联系人昵称
        #   群聊: sessionType="group", groupName=群名, sourceName=群内发送者
        session_type = data.get("sessionType", "")
        source_name = data.get("sourceName", "") or data.get("source", "")
        group_name = data.get("groupName", "")
        talker_name = data.get("talkerName", "") or data.get("talker", "")

        if not source_name and not group_name:
            logger.debug(f"无法确定发送者: {json.dumps(data, ensure_ascii=False)[:200]}")
            return

        is_group = session_type == "group"

        if is_group and group_name:
            # 群聊：chat_name = 群名（用于导航和回复），sender = 发送者
            chat_name = group_name
            sender = source_name or talker_name
        else:
            # 私聊：chat_name = sender = 联系人
            chat_name = source_name or talker_name
            sender = source_name or talker_name

        msg_type_str = "group" if is_group else "friend"

        # 输出原始数据以便调试
        logger.debug(
            f"WeFlow parsed: chat={chat_name!r} sender={sender!r} "
            f"is_group={is_group} sessionType={session_type!r} "
            f"groupName={group_name!r} content={content_raw[:50]!r}"
        )

        message = Message(
            chat_name=chat_name,
            sender=sender,
            content=content_raw,
            msg_type=msg_type_str,
            raw=data,
        )
        self._queue.put(message)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_search_term(name: str) -> str:
        """Strip special characters that trigger web-search in WeChat.

        Keeps Chinese characters, ASCII letters/digits, and spaces.
        "人人人人？&" → "人人人人"
        """
        result: list[str] = []
        for ch in name:
            # Chinese character range
            if "一" <= ch <= "鿿":
                result.append(ch)
            # ASCII alphanumeric
            elif "a" <= ch.lower() <= "z" or "0" <= ch <= "9":
                result.append(ch)
            # Keep spaces as-is
            elif ch == " ":
                result.append(ch)
            # Everything else: skip
        cleaned = "".join(result).strip()
        # Fallback: if everything was stripped, return original
        return cleaned if cleaned else name

    # ------------------------------------------------------------------
    # Win32 window helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_wechat_hwnd():
        """Find the WeChat main window handle via Win32 API.

        Searches for windows with "微信" in the title.  Returns the
        first visible, non-minimized match, or None.
        """
        import win32gui  # type: ignore[import-untyped]
        import win32con  # type: ignore[import-untyped]

        result = []

        def callback(hwnd, _extra):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            if "微信" in title:
                # Skip minimized windows
                if win32gui.IsIconic(hwnd):
                    return True
                result.append(hwnd)
            return True

        win32gui.EnumWindows(callback, None)

        if result:
            logger.debug(f"找到 {len(result)} 个微信窗口: {[win32gui.GetWindowText(h) for h in result]}")
            # Prefer "微信" exact match over longer titles
            for hwnd in result:
                if win32gui.GetWindowText(hwnd) == "微信":
                    return hwnd
            return result[0]
        return None

    @staticmethod
    def _force_foreground(hwnd) -> None:
        """Bring *hwnd* to the foreground, bypassing Windows restrictions.

        Uses ``AttachThreadInput`` to temporarily link the calling
        thread's input queue with the foreground thread, allowing
        ``SetForegroundWindow`` to succeed even when called from a
        background process.
        """
        import win32gui  # type: ignore[import-untyped]
        import win32con  # type: ignore[import-untyped]
        import win32process  # type: ignore[import-untyped]
        import win32api  # type: ignore[import-untyped]

        try:
            # Restore if minimized
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.2)

            # AttachThreadInput trick (from AstrBot bridge)
            foreground_hwnd = win32gui.GetForegroundWindow()
            current_tid = win32api.GetCurrentThreadId()
            foreground_tid = win32process.GetWindowThreadProcessId(foreground_hwnd)[0]
            target_tid = win32process.GetWindowThreadProcessId(hwnd)[0]

            if current_tid != foreground_tid:
                win32process.AttachThreadInput(current_tid, foreground_tid, True)
            if current_tid != target_tid:
                win32process.AttachThreadInput(current_tid, target_tid, True)

            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.2)

        except Exception as e:
            logger.debug(f"AttachThreadInput 失败: {e}，尝试直接激活")
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass

    @staticmethod
    def _get_window_rect(hwnd):
        """Return (left, top, right, bottom) for *hwnd*, or None."""
        import win32gui  # type: ignore[import-untyped]

        try:
            return win32gui.GetWindowRect(hwnd)
        except Exception:
            return None
