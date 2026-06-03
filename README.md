# WeChat Group Bot (微信群聊机器人)

一个基于 [WeFlow](https://weflow.top) + [DeepSeek API](https://api.deepseek.com) 的**微信桌面端群聊机器人**。

- 通过 `/` 命令响应群聊中的消息
- 支持自定义命令扩展
- 内置 AI 笑点解析和对话功能

---

## 项目结构

```
wechat-bot/
├── main.py                     # 入口
├── config.json                 # 配置文件
├── start_bot.bat               # Windows 一键启动脚本
├── requirements.txt            # Python 依赖
├── bot/
│   ├── bot_core.py             # 主循环：轮询消息 → 路由命令
│   ├── command_handler.py      # 命令注册/解析/分发
│   ├── config.py               # 配置管理
│   ├── wechat_client.py        # 微信客户端工厂（根据 config 选择后端）
│   ├── wechat_client_weflow.py # WeFlow 后端（推荐，支持任意微信版本）
│   ├── deepseek_client.py      # DeepSeek API 封装
│   ├── message_store.py        # 消息历史持久化（JSONL 文件）
│   └── send_confirm.py         # 发送确认弹窗（tkinter 子进程）
├── commands/
│   ├── basic.py                # 基础命令：/ping /help /status /echo /time /stop
│   └── entertainment.py        # AI 命令：/笑点解析 /chat
└── message_history.jsonl       # 消息历史文件（运行时生成，gitignore）
```

---

## 工作原理

```
微信桌面版 (登录并可见)
    │
    │ WeFlow 读取微信消息数据库
    ▼
WeFlow (本地工具, 端口 5031)
    │ SSE 推送: /api/v1/push/messages
    ▼
wechat_client_weflow.py (后台线程接收)
    │
    ▼
bot_core.py (主循环)
    ├─ 去重 → 存入消息历史
    ├─ 解析 /command
    ├─ 非命令 → 忽略（可扩展 AI 对话）
    └─ 命令 → 执行 → DeepSeek API（如需）
    │
    ▼
send_confirm.py (发送确认弹窗, 5秒倒计时)
    │
    ▼
pyautogui 模拟键盘
    Ctrl+F 搜索群名 → Enter 打开 → Ctrl+V 粘贴 → Enter 发送
    │
    ▼
微信桌面端 (消息发出)
```

---

## 前置条件

- **Windows 10/11**
- **微信桌面版**（任意版本，已登录，窗口可见）
- **[WeFlow](https://weflow.top)**（下载安装，开启「API 服务」+「主动推送」）
- **Python 3.8+**
- **DeepSeek API Key**（可选，仅 `/笑点解析` 和 `/chat` 命令需要）

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

编辑 `config.json`：

```json
{
    "backend": "weflow",
    "weflow_access_token": "你的WeFlow_Access_Token",
    "bot_nicknames": ["你的微信昵称"],
    "deepseek_api_key": "你的DeepSeek_API_Key"
}
```

| 配置项 | 说明 |
|--------|------|
| `backend` | `"weflow"`（推荐）或 `"wxauto"`（仅微信 3.9.x） |
| `weflow_access_token` | WeFlow → 设置 → Access Token |
| `bot_nicknames` | 机器人的微信昵称（用于检测 @提及） |
| `deepseek_api_key` | DeepSeek API Key（[获取地址](https://platform.deepseek.com/api_keys)） |

### 3. 启动

```bash
# 方式一：命令行
python main.py

# 方式二：双击
start_bot.bat
```

启动后会在屏幕上弹出一个终端窗口，bot 在后台运行。按 `Ctrl+C` 停止。

---

## 内置命令

### 基础命令

| 命令 | 说明 |
|------|------|
| `/ping` | 测试 bot 是否在线 |
| `/help [命令]` | 列出所有命令或查看指定命令详情 |
| `/status` | 查看运行时间、消息数等 |
| `/echo <msg>` | 原样返回消息 |
| `/time` | 显示当前时间 |
| `/stop confirm` | 停止 bot |
| `/confirm-on` | 重新开启发送确认弹窗 |

### AI 命令

| 命令 | 说明 |
|------|------|
| `/笑点解析` | 分析前 10 条消息的笑点 |
| `/笑点解析 -s 8 -e 2` | 分析前 8 条到前 2 条之间的消息 |
| `/chat <消息>` | 与 AI 多轮对话（按群独立上下文） |
| `/chat -s <消息>` | 与 AI 对话 + 联网搜索（DuckDuckGo） |

---

## 发送确认弹窗

bot 发送每条回复前会弹出一个 5 秒倒计时窗口：

- **不操作**：倒计时结束自动发送
- **点击窗口**：挂起，再点发送
- **点击"不再提醒"**：关闭弹窗，后续直接发送

关闭后可用 `/confirm-on` 重新开启。

---

## 添加新命令

在 `commands/` 目录下新建 `.py` 文件，使用装饰器注册：

```python
from bot.command_handler import get_registry, CommandContext

r = get_registry()

@r.register("mycmd", description="我的命令", usage="/mycmd <参数>")
def cmd_mycmd(args: list[str], ctx: CommandContext) -> str:
    # ctx.chat_name, ctx.sender, ctx.is_group 可用
    return f"你好 {ctx.sender}，你说了: " + " ".join(args)
```

bot 重启后自动发现并加载。

---

## 注意事项

### 微信使用

- **微信窗口必须保持可见**，不能最小化（bot 通过模拟键盘操作发送消息）
- **bot 发送消息时会抢窗口焦点**（弹出微信窗口、模拟按键），建议勾选"不再提醒"避免频繁弹窗
- 如果群名包含特殊字符，Ctrl+F 搜索可能不稳定

### WeFlow

- WeFlow 需要保持运行（最小化到托盘即可）
- 确保「API 服务」和「主动推送」都已开启
- 如果 bot 收不到消息，检查 WeFlow 的 Access Token 是否正确

### DeepSeek API

- 免费 API 有速率限制，频繁调用可能被限流
- 限流时 `/笑点解析` 会返回错误提示，/ping 等基础命令不受影响
- 网络环境可能需要绕过代理才能访问 `api.deepseek.com`

### 消息历史

- 消息记录持久化在 `message_history.jsonl`，重启 bot 后保留
- 该文件包含群聊内容，**不要分享给他人**
- 已在 `.gitignore` 中排除

---

## License

MIT
