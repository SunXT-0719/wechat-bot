"""
多语言文案 — 供基础命令使用。
"""

from __future__ import annotations

from bot.language import get as _lang, get_name as _lang_name, lang_prompt_instr as _lang_instr

# key → {zh, en, jp}
_T = {
    "pong": {
        "zh": "🏓 pong!",
        "en": "🏓 pong!",
        "jp": "🏓 ポン！",
    },
    "echo_prefix": {
        "zh": "🔊 ",
        "en": "🔊 ",
        "jp": "🔊 ",
    },
    "echo_usage": {
        "zh": "用法: /echo <消息内容>",
        "en": "Usage: /echo <message>",
        "jp": "使い方: /echo <メッセージ>",
    },
    "time_prefix": {
        "zh": "🕐 当前时间: ",
        "en": "🕐 Current time: ",
        "jp": "🕐 現在時刻: ",
    },
    "stop_confirm": {
        "zh": "⚠️ 确定要停止机器人吗？输入 /stop confirm 确认。",
        "en": "⚠️ Are you sure? Type /stop confirm to proceed.",
        "jp": "⚠️ ボットを停止しますか？ /stop confirm で確認。",
    },
    "stop_ok": {
        "zh": "👋 机器人正在停止...",
        "en": "👋 Bot is stopping...",
        "jp": "👋 ボットを停止中...",
    },
    "stop_fail": {
        "zh": "⚠️ 无法停止（bot 引用不可用）",
        "en": "⚠️ Cannot stop (bot reference unavailable)",
        "jp": "⚠️ 停止できません（bot参照不可）",
    },
    "confirm_on": {
        "zh": "✅ 发送确认弹窗已重新开启",
        "en": "✅ Send confirmation popup re-enabled",
        "jp": "✅ 送信確認ポップアップを再有効化しました",
    },
    "confirm_already": {
        "zh": "ℹ️ 发送确认弹窗本来就是开启的",
        "en": "ℹ️ Send confirmation popup is already enabled",
        "jp": "ℹ️ 送信確認ポップアップは既に有効です",
    },
    "unknown_cmd": {
        "zh": "❓ 未知命令: {cmd}\n可用命令: {cmds}\n输入 /help 查看更多信息",
        "en": "❓ Unknown command: {cmd}\nAvailable: {cmds}\nType /help for more",
        "jp": "❓ 不明なコマンド: {cmd}\n利用可能: {cmds}\n/help で詳細",
    },
    "cmd_error": {
        "zh": "⚠️ 命令 {cmd} 执行时发生内部错误，请检查日志。",
        "en": "⚠️ Internal error executing command {cmd}. Check logs.",
        "jp": "⚠️ コマンド {cmd} の実行中に内部エラーが発生しました。",
    },
    "status_header": {
        "zh": "📊 机器人状态",
        "en": "📊 Bot Status",
        "jp": "📊 ボットステータス",
    },
    "status_uptime": {
        "zh": "   运行时间: {uptime}",
        "en": "   Uptime: {uptime}",
        "jp": "   稼働時間: {uptime}",
    },
    "status_msgs": {
        "zh": "   处理消息: {count} 条",
        "en": "   Messages processed: {count}",
        "jp": "   処理メッセージ: {count} 件",
    },
    "status_cmds": {
        "zh": "   已注册命令: {count} 个",
        "en": "   Commands registered: {count}",
        "jp": "   登録コマンド: {count} 個",
    },
    "status_sys": {
        "zh": "   系统: {sys}",
        "en": "   OS: {sys}",
        "jp": "   OS: {sys}",
    },
    "status_py": {
        "zh": "   Python: {py}",
        "en": "   Python: {py}",
        "jp": "   Python: {py}",
    },
    "status_lang": {
        "zh": "   语言: {lang}",
        "en": "   Language: {lang}",
        "jp": "   言語: {lang}",
    },
    "help_header": {
        "zh": "📋 可用命令:",
        "en": "📋 Available commands:",
        "jp": "📋 利用可能なコマンド:",
    },
    "help_footer": {
        "zh": "输入 /help <命令名> 查看命令详细用法",
        "en": "Type /help <command> for details",
        "jp": "/help <コマンド名> で詳細を表示",
    },
    "help_not_found": {
        "zh": "❓ 未找到命令: {cmd}",
        "en": "❓ Command not found: {cmd}",
        "jp": "❓ コマンドが見つかりません: {cmd}",
    },
    "help_desc_fmt": {
        "zh": "   描述: {desc}",
        "en": "   Description: {desc}",
        "jp": "   説明: {desc}",
    },
    "help_usage_fmt": {
        "zh": "   用法: {usage}",
        "en": "   Usage: {usage}",
        "jp": "   使い方: {usage}",
    },
    "help_no_desc": {
        "zh": "(无)",
        "en": "(none)",
        "jp": "(なし)",
    },
    "help_no_desc_item": {
        "zh": "(无描述)",
        "en": "(no description)",
        "jp": "(説明なし)",
    },
    "joke_parse_error_s": {
        "zh": "❌ -s 参数必须是正整数",
        "en": "❌ -s must be a positive integer",
        "jp": "❌ -s は正の整数で指定してください",
    },
    "joke_parse_error_e": {
        "zh": "❌ -e 参数必须是正整数",
        "en": "❌ -e must be a positive integer",
        "jp": "❌ -e は正の整数で指定してください",
    },
    "joke_unknown_arg": {
        "zh": "❌ 未知参数: {arg}\n用法: /笑点解析 [-s K] [-e M]",
        "en": "❌ Unknown arg: {arg}\nUsage: /joke [-s K] [-e M]",
        "jp": "❌ 不明な引数: {arg}\n使い方: /笑点解析 [-s K] [-e M]",
    },
    "joke_k_m_positive": {
        "zh": "❌ K 和 M 必须是正整数",
        "en": "❌ K and M must be positive integers",
        "jp": "❌ K と M は正の整数で指定してください",
    },
    "joke_k_gt_m": {
        "zh": "❌ K({k}) 必须大于 M({m})",
        "en": "❌ K({k}) must be greater than M({m})",
        "jp": "❌ K({k}) は M({m}) より大きくなければなりません",
    },
    "joke_no_history": {
        "zh": "❌ 没有足够的聊天记录（bot 启动后才会记录消息）。\n请先聊几段天再试！",
        "en": "❌ Not enough chat history.\nChat a bit first and try again!",
        "jp": "❌ チャット履歴が不足しています。\n先に会話をしてから再試行してください。",
    },
    "joke_bot_error": {
        "zh": "❌ 内部错误：无法获取 bot 配置",
        "en": "❌ Internal error: cannot get bot config",
        "jp": "❌ 内部エラー: bot設定を取得できません",
    },
    "joke_api_fail": {
        "zh": "❌ AI 调用失败（网络超时或 API 限流），请稍后重试。\n提示：DeepSeek 免费 API 有速率限制，频繁调用会暂时被封。",
        "en": "❌ AI call failed (timeout or rate limit). Try later.\nTip: DeepSeek free API has rate limits.",
        "jp": "❌ AI呼び出しに失敗しました（タイムアウトまたはレート制限）。後で再試行してください。",
    },
    "chat_usage": {
        "zh": "用法: /chat <消息内容>",
        "en": "Usage: /chat <message>",
        "jp": "使い方: /chat <メッセージ>",
    },
    "chat_bot_error": {
        "zh": "❌ 内部错误：无法获取 bot 配置",
        "en": "❌ Internal error: cannot get bot config",
        "jp": "❌ 内部エラー: bot設定を取得できません",
    },
    "chat_api_fail": {
        "zh": "❌ AI 调用失败，请稍后重试",
        "en": "❌ AI call failed, try later",
        "jp": "❌ AI呼び出しに失敗しました。後で再試行してください",
    },
    "clear_usage": {
        "zh": "用法: /clear <密钥>",
        "en": "Usage: /clear <key>",
        "jp": "使い方: /clear <キー>",
    },
    "clear_wrong_key": {
        "zh": "❌ 密钥错误",
        "en": "❌ Wrong key",
        "jp": "❌ キーが間違っています",
    },
    "clear_ok": {
        "zh": "✅ 上下文已清空，新密钥已发送给 {owner}",
        "en": "✅ Context cleared. New key sent to {owner}",
        "jp": "✅ コンテキストをクリアしました。新しいキーを {owner} に送信しました",
    },
    "clear_key_msg": {
        "zh": "🔑 初始密钥: {code}\n使用 /clear {code} 可清空当前群的 chat 上下文。\n密钥每次使用后会重置并重新发送。",
        "en": "🔑 Initial key: {code}\nUse /clear {code} to clear chat context.\nKey resets after each use.",
        "jp": "🔑 初期キー: {code}\n/clear {code} でチャットコンテキストをクリア。\nキーは使用後にリセットされます。",
    },
    "clear_new_key": {
        "zh": "🔑 新密钥: {code}",
        "en": "🔑 New key: {code}",
        "jp": "🔑 新しいキー: {code}",
    },
    "lang_usage": {
        "zh": "用法: /language <中/Eng/日> <密钥>\n例如: /language Eng 1234\n（密钥与 /clear 共用，仅对当前群生效）",
        "en": "Usage: /language <中/Eng/日> <key>\nExample: /language Eng 1234\n(Key shared with /clear, per-chat only)",
        "jp": "使い方: /language <中/Eng/日> <キー>\n例: /language Eng 1234\n（キーは /clear と共通、現在のグループのみ）",
    },
    "lang_unknown": {
        "zh": "❌ 未知语言: {lang}\n支持: 中 / Eng / 日",
        "en": "❌ Unknown language: {lang}\nSupported: 中 / Eng / 日",
        "jp": "❌ 不明な言語: {lang}\n対応: 中 / Eng / 日",
    },
    "lang_ok": {
        "zh": "✅ 语言已切换为: {lang}",
        "en": "✅ Language switched to: {lang}",
        "jp": "✅ 言語を切り替えました: {lang}",
    },
    "lang_wrong_key": {
        "zh": "❌ 密钥错误",
        "en": "❌ Wrong key",
        "jp": "❌ キーが間違っています",
    },
    "rp_usage": {
        "zh": "用法: /roleplay -show | -set <提示词> | -clear\n密钥与 /clear 共用",
        "en": "Usage: /roleplay -show | -set <prompt> | -clear\nKey shared with /clear",
        "jp": "使い方: /roleplay -show | -set <プロンプト> | -clear\nキーは /clear と共通",
    },
    "rp_show": {
        "zh": "📋 当前角色扮演提示词:\n{prompt}",
        "en": "📋 Current roleplay prompt:\n{prompt}",
        "jp": "📋 現在のロールプレイプロンプト:\n{prompt}",
    },
    "rp_set_usage": {
        "zh": "用法: /roleplay -set <提示词>\n例如: /roleplay -set 你是一只傲娇猫娘",
        "en": "Usage: /roleplay -set <prompt>\nExample: /roleplay -set You are a tsundere cat girl",
        "jp": "使い方: /roleplay -set <プロンプト>\n例: /roleplay -set あなたはツンデレ猫娘です",
    },
    "rp_set_ok": {
        "zh": "✅ 已选用角色扮演套件（仅对当前群生效）",
        "en": "✅ Roleplay set (this chat only, use /chat to try)",
        "jp": "✅ ロールプレイを設定しました（このグループのみ、/chat で試してください）",
    },
    "rp_not_found": {
        "zh": "❌ 未找到角色扮演套件: {name}",
        "en": "❌ Roleplay not found: {name}",
        "jp": "❌ ロールプレイが見つかりません: {name}",
    },
    "rp_list": {
        "zh": "📋 可用角色扮演套件:",
        "en": "📋 Available roleplay sets:",
        "jp": "📋 利用可能なロールプレイ:",
    },
    "rp_list_empty": {
        "zh": "ℹ️ 暂无角色扮演套件。使用 /roleplay -new 创建。",
        "en": "ℹ️ No roleplay sets. Use /roleplay -new to create.",
        "jp": "ℹ️ ロールプレイがありません。/roleplay -new で作成。",
    },
    "rp_new_usage": {
        "zh": "用法: /roleplay -new <名称> <提示词内容>",
        "en": "Usage: /roleplay -new <name> <prompt content>",
        "jp": "使い方: /roleplay -new <名前> <プロンプト内容>",
    },
    "rp_new_ok": {
        "zh": "✅ 已创建角色扮演套件「{name}」并设为当前群使用",
        "en": "✅ Created roleplay set [{name}] and applied to this chat",
        "jp": "✅ ロールプレイ「{name}」を作成し、このグループに適用しました",
    },
    "rp_edit_ok": {
        "zh": "✅ 已更新角色扮演套件「{name}」（未切换当前群选择）",
        "en": "✅ Updated roleplay set [{name}] (current chat not changed)",
        "jp": "✅ ロールプレイ「{name}」を更新しました（現在のグループは変更なし）",
    },
    "rp_set_usage": {
        "zh": "用法: /roleplay -set <名称>\n先用 /roleplay -list 查看可用套件",
        "en": "Usage: /roleplay -set <name>\nUse /roleplay -list to see available sets",
        "jp": "使い方: /roleplay -set <名前>\n/roleplay -list で利用可能なセットを表示",
    },
    "rp_clear_ok": {
        "zh": "✅ 角色扮演已清除，恢复默认 chat 模式",
        "en": "✅ Roleplay cleared, back to default chat mode",
        "jp": "✅ ロールプレイを解除し、デフォルトチャットモードに戻しました",
    },
    "rp_unknown": {
        "zh": "❌ 未知参数: {arg}\n用法: /roleplay -show | -set <提示词> | -clear",
        "en": "❌ Unknown arg: {arg}\nUsage: /roleplay -show | -set <prompt> | -clear",
        "jp": "❌ 不明な引数: {arg}\n使い方: /roleplay -show | -set | -clear",
    },
    "reset_usage": {
        "zh": "用法: /reset <旧密钥>",
        "en": "Usage: /reset <old key>",
        "jp": "使い方: /reset <旧キー>",
    },
    "reset_wrong_key": {
        "zh": "❌ 密钥错误",
        "en": "❌ Wrong key",
        "jp": "❌ キーが間違っています",
    },
    "reset_ok": {
        "zh": "✅ 密钥已重置，新密钥已发送给 {owner}",
        "en": "✅ Key reset, new key sent to {owner}",
        "jp": "✅ キーをリセット、新しいキーを {owner} に送信しました",
    },
}


# 全局上下文：由 bot_core 在执行命令前设置
_current_chat: str = ""


def set_chat_context(chat_id: str) -> None:
    global _current_chat
    _current_chat = chat_id


def t(key: str, **kwargs) -> str:
    """返回当前群聊语言的文案，支持 {key} 格式化。"""
    chat_id = kwargs.pop("_chat", "") or _current_chat
    lang = _lang(chat_id)
    entry = _T.get(key, {})
    text = entry.get(lang) or entry.get("zh", key)
    if kwargs:
        text = text.format(**kwargs)
    return text
