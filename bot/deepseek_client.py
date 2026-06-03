"""
DeepSeek API client (OpenAI-compatible).

Used by commands that need LLM-based analysis of chat content.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

# System-wide proxy often blocks direct HTTPS connections on Chinese
# networks.  We bypass it here so the bot can reach api.deepseek.com.
_NO_PROXY = {"http": None, "https": None}


def call_deepseek(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1024,
    timeout: int = 60,
) -> str | None:
    """Send a single-turn chat-completion request to DeepSeek.

    Returns the assistant's text, or ``None`` on failure.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.8,
    }

    try:
        resp = requests.post(
            base_url,
            headers=headers,
            json=payload,
            timeout=timeout,
            proxies=_NO_PROXY,  # bypass system proxy
        )

        if resp.status_code != 200:
            logger.error(
                f"DeepSeek API 返回 {resp.status_code}: "
                f"{resp.text[:300]}"
            )
            return None

        body = resp.json()
        choice = body["choices"][0]
        content: str = choice["message"]["content"]
        return content.strip()

    except requests.ConnectionError:
        logger.exception("无法连接 DeepSeek API（请检查网络/代理设置）")
        return None
    except Exception:
        logger.exception("DeepSeek API 调用异常")
        return None


# ---------------------------------------------------------------------------
# Web search (DuckDuckGo, free, no API key)
# ---------------------------------------------------------------------------

def search_web(query: str, max_results: int = 5) -> str:
    """Search DuckDuckGo and return formatted results."""
    try:
        from ddgs import DDGS  # type: ignore[import-untyped]

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                title = r.get("title", "")
                body = r.get("body", "")
                href = r.get("href", "")
                results.append(f"- {title}\n  {body}\n  {href}")

        if not results:
            return "(未找到搜索结果)"

        return "\n\n".join(results)
    except ImportError:
        return "(搜索不可用：缺少 ddgs 包，请运行 pip install ddgs)"
    except Exception:
        logger.exception("网页搜索失败")
        return "(搜索失败)"


def call_deepseek_messages(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = 512,
    timeout: int = 60,
) -> str | None:
    """Send a multi-turn chat-completion request (messages array)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.8,
    }

    try:
        resp = requests.post(
            base_url,
            headers=headers,
            json=payload,
            timeout=timeout,
            proxies=_NO_PROXY,
        )

        if resp.status_code != 200:
            logger.error(
                f"DeepSeek API 返回 {resp.status_code}: "
                f"{resp.text[:300]}"
            )
            return None

        body = resp.json()
        choice = body["choices"][0]
        content: str = choice["message"]["content"]
        return content.strip()

    except requests.ConnectionError:
        logger.exception("无法连接 DeepSeek API（请检查网络/代理设置）")
        return None
    except Exception:
        logger.exception("DeepSeek API 调用异常")
        return None


# ---------------------------------------------------------------------------
# Web search (DuckDuckGo, free, no API key)
# ---------------------------------------------------------------------------

def search_web(query: str, max_results: int = 5) -> str:
    """Search DuckDuckGo and return formatted results."""
    try:
        from ddgs import DDGS  # type: ignore[import-untyped]

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                title = r.get("title", "")
                body = r.get("body", "")
                href = r.get("href", "")
                results.append(f"- {title}\n  {body}\n  {href}")

        if not results:
            return "(未找到搜索结果)"

        return "\n\n".join(results)
    except ImportError:
        return "(搜索不可用：缺少 ddgs 包，请运行 pip install ddgs)"
    except Exception:
        logger.exception("网页搜索失败")
        return "(搜索失败)"
