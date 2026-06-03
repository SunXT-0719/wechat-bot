"""
WeChat 群聊机器人 — 入口点

用法:
    python main.py [--config config.json]

依赖:
    pip install -r requirements.txt

前置条件:
    - **WeFlow 后端** (推荐): 下载并运行 WeFlow (https://weflow.top),
      在 WeFlow 中开启 "API 服务" + "主动推送"，将 Access Token 填入 config.json
    - **wxauto 后端**: 微信 3.9.x 桌面版已安装并登录，窗口可见
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# 确保项目根目录在 sys.path 中，以便 "import bot" 和 "import commands" 工作
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def setup_logging(log_file: str, log_level: str) -> None:
    """Configure the root logger to output to both console and file."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件 handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(fmt)

    # 控制台 handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(fh)
    root.addHandler(ch)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WeChat 群聊机器人",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python main.py                     # 使用默认 config.json
    python main.py --config myconf.json
        """,
    )
    parser.add_argument(
        "--config",
        default=None,
        help="配置文件路径 (默认: config.json)",
    )
    args = parser.parse_args()

    # ---- 先加载配置以便设置日志 ----------------------------------------
    from bot.config import BotConfig

    config = BotConfig(args.config)
    setup_logging(config.log_file, config.log_level)

    logger = logging.getLogger(__name__)

    # ---- 前置检查 ----------------------------------------------------
    _check_environment(config)

    # ---- 初始化并启动 ------------------------------------------------
    from bot.bot_core import WeChatBot

    bot = WeChatBot(config_path=args.config)

    logger.info(f"后端: {config.backend}")
    logger.info("正在启动微信机器人...")
    bot.start()


def _check_environment(config) -> None:
    """Check that the required dependencies for the selected backend exist."""
    logger = logging.getLogger(__name__)

    # 公共依赖
    common_deps = ["pyperclip", "requests"]
    # 各后端特有依赖
    backend_deps: dict[str, list[str]] = {
        "wxauto": ["wxauto", "uiautomation"],
        "weflow": ["pyautogui", "pygetwindow"],
    }

    backend = config.backend
    required = common_deps + backend_deps.get(backend, [])

    missing = []
    for mod_name in required:
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(mod_name)

    if missing:
        logger.error(
            f"缺少依赖 ({backend} 后端): {', '.join(missing)}\n"
            f"请运行: pip install -r requirements.txt"
        )
        sys.exit(1)

    # 特定于 WeFlow 后端的检查
    if backend == "weflow":
        if not config.weflow_access_token or config.weflow_access_token.startswith("你的"):
            logger.warning(
                "⚠️  WeFlow Access Token 未设置！\n"
                "   1. 打开 WeFlow → 设置 → 复制 Access Token\n"
                "   2. 粘贴到 config.json 的 weflow_access_token 字段"
            )

    logger.info(f"环境检查通过 ✓ (后端: {backend})")


if __name__ == "__main__":
    main()
