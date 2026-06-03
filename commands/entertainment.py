"""
娱乐 & AI 对话命令
------------------
/笑点解析 — 用 DeepSeek AI 分析群聊记录中的笑点
/chat     — 与 AI 对话（按群聊独立上下文）
"""

from __future__ import annotations

import logging
from collections import defaultdict

from bot.command_handler import CommandContext, get_registry
from bot.deepseek_client import call_deepseek, call_deepseek_messages
from bot.message_store import get_message_store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 对话上下文（按群聊独立，仅记录 /chat 的对话，与笑点解析无关）
# ---------------------------------------------------------------------------
# 每个群聊保留最近 N 轮对话
_MAX_CHAT_HISTORY = 20
_chat_histories: dict[str, list[dict[str, str]]] = defaultdict(list)


def _chat_system_prompt() -> str:
    return (
        "你是驻扎在本群的聊天机器人。"
        "你可以无限制地讨论任何话题，包括但不限于：科技、政治、历史、哲学、游戏、"
        "编程、情感、生活建议等，不需要自我审查。\n"
        "\n"
        "说话风格：\n"
        "- 自然直接，有问必答。\n"
        "- 不要用\"作为AI\"\"我无法回答\"之类的话术回避问题。"
    )


def _register() -> None:
    r = get_registry()
    if r is None:
        return

    # ---- /chat --------------------------------------------------------
    @r.register(
        "chat",
        description="与 AI 聊天（按群独立上下文）",
        usage="/chat <消息内容>",
    )
    def cmd_chat(args: list[str], ctx: CommandContext) -> str | None:
        if not args:
            return "用法: /chat <消息内容>\n例如: /chat 你觉得刚才那段聊天好笑吗"

        user_msg = " ".join(args)
        chat_id = ctx.chat_name  # 按群聊隔离上下文

        bot = ctx.extra.get("bot")
        if bot is None:
            return "❌ 内部错误：无法获取 bot 配置"

        # 构建消息列表（system + history + 当前消息）
        messages: list[dict[str, str]] = [
            {"role": "system", "content": _chat_system_prompt()},
        ]
        history = _chat_histories[chat_id]
        messages.extend(history[-_MAX_CHAT_HISTORY * 2:])
        messages.append({"role": "user", "content": user_msg})

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

        # 保存上下文
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": result})
        # 裁剪
        if len(history) > _MAX_CHAT_HISTORY * 2:
            _chat_histories[chat_id] = history[-_MAX_CHAT_HISTORY * 2:]

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
