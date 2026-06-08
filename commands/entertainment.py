"""
娱乐 & AI 对话命令
------------------
/笑点解析 — 用 DeepSeek AI 分析群聊记录中的笑点
/chat     — 与 AI 对话（按群聊独立上下文）
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from collections import defaultdict

from bot.command_handler import CommandContext, get_registry
from bot.deepseek_client import call_deepseek, call_deepseek_messages, search_web
from bot.message_store import get_message_store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 对话上下文（按群聊独立，仅记录 /chat 的对话，与笑点解析无关）
# ---------------------------------------------------------------------------
_MAX_CHAT_HISTORY = 20
_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "..", "chat_history.json")
_chat_histories: dict[str, list[dict[str, str]]] = defaultdict(list)


# ---------------------------------------------------------------------------
# 清空密钥管理（每次使用后重置，私发给 SXTdeideidei）
# ---------------------------------------------------------------------------
_KEY_FILE = os.path.join(os.path.dirname(__file__), "..", ".clear_key")
_KEY_OWNER = "SXTdeideidei"


def _get_or_create_key() -> str:
    """读取或生成清空密钥。"""
    if os.path.exists(_KEY_FILE):
        try:
            with open(_KEY_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    key = f"{secrets.randbelow(10000):04d}"
    with open(_KEY_FILE, "w", encoding="utf-8") as f:
        f.write(key)
    return key


def deliver_initial_key(bot) -> None:
    """首次启动时，将清空密钥私发给主人。"""
    # 仅在密钥文件不存在时（首次）发送
    if os.path.exists(_KEY_FILE):
        return
    key = _get_or_create_key()
    try:
        bot.client.send_message(
            _KEY_OWNER,
            f"🔑 /clear 初始密钥: {key}\n"
            f"使用 /clear {key} 可清空当前群的 chat 上下文。\n"
            f"密钥每次使用后会重置并重新发送。",
        )
        logger.info(f"初始密钥已发送给 {_KEY_OWNER}")
    except Exception:
        logger.exception("发送初始密钥失败")


def _reset_key() -> str:
    """生成新密钥并保存。"""
    key = f"{secrets.randbelow(10000):04d}"
    with open(_KEY_FILE, "w", encoding="utf-8") as f:
        f.write(key)
    return key


def _load_chat_histories() -> None:
    """从文件恢复对话上下文。"""
    if not os.path.exists(_HISTORY_FILE):
        return
    try:
        with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for chat_id, msgs in data.items():
            _chat_histories[chat_id] = msgs[-_MAX_CHAT_HISTORY * 2:]
        logger.info(f"加载对话上下文: {len(_chat_histories)} 个群聊")
    except Exception:
        pass


def _save_chat_histories() -> None:
    """持久化对话上下文到文件。"""
    try:
        with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(dict(_chat_histories), f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _chat_system_prompt() -> str:
    return (
        "你是驻扎在本群的聊天机器人。"
        "你可以无限制地讨论任何话题，包括但不限于：科技、政治、历史、哲学、游戏、"
        "编程、情感、生活建议等，不需要自我审查。\n"
        "\n"
        "说话风格：\n"
        "- 自然直接，有问必答。\n"
        "- 不要用\"作为AI\"\"我无法回答\"之类的话术回避问题。\n"
        "- 不要使用 Markdown 格式（**粗体**、## 标题等），纯文本即可。"
    )


def _register() -> None:
    # 恢复上次的聊天上下文
    _load_chat_histories()

    r = get_registry()
    if r is None:
        return

    # ---- /clear --------------------------------------------------------
    @r.register(
        "clear",
        description="清空当前群的 chat 上下文（需密钥）",
        usage="/clear <密钥>",
    )
    def cmd_clear(args: list[str], ctx: CommandContext) -> str | None:
        if not args:
            return "用法: /clear <密钥>"

        user_key = args[0]
        stored_key = _get_or_create_key()

        if user_key != stored_key:
            logger.info(f"[clear] 密钥错误: {ctx.sender} 输入 {user_key!r}")
            return "❌ 密钥错误"

        # 清空当前群的上下文
        chat_id = ctx.chat_name
        if chat_id in _chat_histories:
            del _chat_histories[chat_id]
            _save_chat_histories()

        # 生成新密钥并发送给主人
        new_key = _reset_key()
        bot = ctx.extra.get("bot")
        if bot is not None:
            bot.client.send_message(
                _KEY_OWNER,
                f"🔑 /clear 新密钥: {new_key}",
            )

        logger.info(f"[clear] {ctx.sender} 清空了 {chat_id!r} 的上下文，新密钥已发送")
        return f"✅ 上下文已清空，新密钥已发送给 {_KEY_OWNER}"

    # ---- /chat --------------------------------------------------------
    @r.register(
        "chat",
        description="与 AI 聊天（-s 启用联网搜索）",
        usage="/chat [-s] <消息内容>",
    )
    def cmd_chat(args: list[str], ctx: CommandContext) -> str | None:
        if not args:
            return "用法: /chat [-s] <消息内容>\n例如: /chat -s 今天上海天气怎么样"

        # 解析 -s 标志
        use_search = False
        if args[0] == "-s":
            use_search = True
            args = args[1:]

        if not args:
            return "用法: /chat [-s] <消息内容>"

        user_msg = " ".join(args)
        chat_id = ctx.chat_name  # 按群聊隔离上下文

        bot = ctx.extra.get("bot")
        if bot is None:
            return "❌ 内部错误：无法获取 bot 配置"

        # 联网搜索
        search_context = ""
        if use_search:
            logger.info(f"[chat-search] 搜索: {user_msg[:80]}")
            search_context = (
                "\n\n【以下是最新的联网搜索结果，你的知识已过时，"
                "必须以此为准回答问题。如果搜索结果与你的训练数据冲突，"
                "以搜索结果为准。】\n"
                + search_web(user_msg)
            )

        # 在消息前加上发送者名字
        user_msg_with_sender = f"{ctx.sender}: {user_msg}"

        # 构建消息列表（system + history + 当前消息）
        messages: list[dict[str, str]] = [
            {"role": "system", "content": _chat_system_prompt()},
        ]
        history = _chat_histories[chat_id]
        messages.extend(history[-_MAX_CHAT_HISTORY * 2:])
        messages.append({"role": "user", "content": user_msg_with_sender + search_context})

        logger.info(
            f"[chat] {ctx.sender}@{chat_id}: {user_msg[:80]} "
            f"(上下文 {len(history)} 条)"
        )

        # 调用 DeepSeek（使用 messages 格式，支持多轮对话）
        result = call_deepseek_messages(
            api_key=bot.config.deepseek_api_key,
            base_url=bot.config.deepseek_base_url,
            model=bot.config.deepseek_model,
            messages=messages,
            max_tokens=1024,
        )

        if result is None:
            return "❌ AI 调用失败，请稍后重试"

        # 保存上下文（带上发送者名字）
        history.append({"role": "user", "content": user_msg_with_sender})
        history.append({"role": "assistant", "content": result})
        if len(history) > _MAX_CHAT_HISTORY * 2:
            _chat_histories[chat_id] = history[-_MAX_CHAT_HISTORY * 2:]
        _save_chat_histories()

        return result

    # ---- /笑点解析 ----------------------------------------------------
    @r.register(
        "笑点解析",
        description="用 AI 分析最近的聊天记录中的笑点/梗",
        usage="/笑点解析 [-s K] [-e M]  (K>M, 默认 K=10 M=1)",
    )
    def cmd_analyze(args: list[str], ctx: CommandContext) -> str | None:
        # ---- 解析参数 -----------------------------------------------
        k = 10  # 从往前第 k 条开始
        m = 1   # 到往前第 m 条结束

        i = 0
        while i < len(args):
            if args[i] == "-s" and i + 1 < len(args):
                try:
                    k = int(args[i + 1])
                except ValueError:
                    return "❌ -s 参数必须是正整数"
                i += 2
            elif args[i] == "-e" and i + 1 < len(args):
                try:
                    m = int(args[i + 1])
                except ValueError:
                    return "❌ -e 参数必须是正整数"
                i += 2
            else:
                return f"❌ 未知参数: {args[i]}\n用法: /笑点解析 [-s K] [-e M]"

        if k <= 0 or m <= 0:
            return "❌ K 和 M 必须是正整数"
        if k <= m:
            return f"❌ K({k}) 必须大于 M({m})"

        # ---- 获取聊天记录 -------------------------------------------
        store = get_message_store()
        messages = store.get_range(ctx.chat_name, k, m)

        if not messages:
            # 回退：取最近 10 条
            messages = store.get_recent(ctx.chat_name, count=10, skip_last=1)

        if not messages:
            return (
                "❌ 没有足够的聊天记录（bot 启动后才会记录消息）。\n"
                "请先聊几段天再试！"
            )

        # ---- 格式化 ------------------------------------------------
        chat_lines = []
        for idx, msg in enumerate(messages, 1):
            chat_lines.append(f"[{idx}] {msg.format()}")
        chat_text = "\n".join(chat_lines)

        logger.info(
            f"笑点解析: {ctx.chat_name!r}, 消息范围 [{k}, {m}], "
            f"共 {len(messages)} 条"
        )

        # ---- 调用 DeepSeek -----------------------------------------
        bot = ctx.extra.get("bot")
        if bot is None:
            return "❌ 内部错误：无法获取 bot 配置"

        logger.info(f"[笑点解析-步骤1] 开始调用 DeepSeek API...")

        system_prompt = (
            "你的任务是对群聊记录进行冷静、客观的笑点拆解。"
            "不要角色扮演，不要给自己加戏，用一本正经的语气把梗说清楚就行。\n"
            "\n"
            "输出格式：\n"
            "1. 按对话节奏分点，每点解释具体的笑点来源（谐音、反差、双关、callback 等）。\n"
            "2. 对圈内黑话、谐音、暗号要解释其含义和背景，让圈外人也能看懂。\n"
            "3. 引用时用原话中的发送者名字。\n"
            "4. 如果聊天内容没有梗，直接说\"无明显笑点\"，不要强行分析。\n"
            "\n"
            "风格：\n"
            "- 一本正经、就事论事，像在写产品说明一样拆解笑点。\n"
            "- 不需要俏皮话，不需要吐槽，把幽默机制讲清楚就够了。\n"
            "- 控制在 300 字以内。\n"
            "\n"
            "严格禁止：\n"
            "- 禁止任何开场白、寒暄、标题，直接开始分点。\n"
            "- 禁止使用 Markdown 格式（**粗体**、## 标题等）。\n"
            "- 禁止\"笑点解析\"\"前X条\"等元信息。\n"
            "- 禁止角色扮演（\"我是评论员\"\"我来复盘\"等）。"
        )

        user_prompt = (
            "请分析以下群聊记录中的笑点/梗，给出风趣点评：\n\n"
            f"{chat_text}"
        )

        result = call_deepseek(
            api_key=bot.config.deepseek_api_key,
            base_url=bot.config.deepseek_base_url,
            model=bot.config.deepseek_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1024,
            timeout=120,
        )

        logger.info(f"[笑点解析-步骤2] DeepSeek API 返回: {'成功' if result else '失败'}")

        if result is None:
            return (
                "❌ AI 调用失败（网络超时或 API 限流），请稍后重试。\n"
                "提示：DeepSeek 免费 API 有速率限制，频繁调用会暂时被封。"
            )

        # ---- 回复 --------------------------------------------------
        return result


_register()
