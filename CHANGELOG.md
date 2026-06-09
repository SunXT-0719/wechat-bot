v2.6 — Web 控制面板
- 新增 Web 可视化控制面板 (默认端口 8765)
- 支持从面板启动/停止机器人，查看运行状态
- 密钥管理：查看和重置 /clear 密钥
- 角色扮演套件管理：创建、编辑、删除、按群分配
- 新增 `start_async()` 非阻塞启动方式
- 新增 `--no-panel` 命令行参数

v2.5 — 角色扮演套件系统、语言免密钥
- 角色扮演改为套件管理模式（-new/-edit/-set/-list/-show/-clear）
- /language 不再需要密钥
- 语言指令改为每次对话追加

v2.4 — 国际化、/reset、/roleplay
- 支持中/Eng/日三语切换（/language）
- 新增 /roleplay 角色扮演
- 新增 /reset 重置密钥
- 所有指令输出跟随语言设定

v2.3 — /clear 密钥、弹窗移除
- 新增 /clear 清空 chat 上下文（密钥保护）
- 移除发送确认弹窗

v2.2 — 消息持久化、上下文优化
- 消息历史持久化到文件
- chat 上下文带发送者名字
- 笑点解析排除 / 命令

v2.1 — /chat 多轮对话
- 新增 /chat 指令，按群独立上下文
- DeepSeek v4-flash 模型

v2.0 — 笑点解析
- 新增 /笑点解析，AI 分析群聊笑点
- 支持 -s/-e 参数控制范围

v1.0 — 基础框架
- WeFlow + pyautogui 微信接入
- 基础命令：/ping /help /status /echo /time /stop
- 消息去重、群聊隔离
