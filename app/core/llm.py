import logging
import os
from typing import Protocol

import httpx

from app.core.config import Config

logger = logging.getLogger("wsnote.llm")


class BaseLLM(Protocol):
    def complete(self, messages: list[dict]) -> str: ...
    def available(self) -> bool: ...


class FakeLLM:
    def complete(self, messages: list[dict]) -> str:
        last = messages[-1]["content"] if messages else ""
        return f"（Fake 回复）针对「{last}」的摘要。"

    def available(self) -> bool:
        return True


class OpenAICompatLLM:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.api_key) and bool(self.base_url)

    def complete(self, messages: list[dict]) -> str:
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def build_llm(config: Config) -> BaseLLM:
    # 环境变量优先（方案 B）：key 不进 git，config.py 保持空
    api_key = os.environ.get("WSNOTE_LLM_API_KEY", config.llm_api_key)
    base_url = os.environ.get("WSNOTE_LLM_BASE_URL", config.llm_base_url)
    model = os.environ.get("WSNOTE_LLM_MODEL", config.llm_model)
    raw_timeout = os.environ.get("WSNOTE_LLM_TIMEOUT", "")
    try:
        timeout = float(raw_timeout) if raw_timeout else config.llm_timeout
    except ValueError:
        timeout = config.llm_timeout
    if not api_key:
        logger.warning("无 LLM key：问答将降级为仅检索")
        return OpenAICompatLLM("", "", model)  # available()=False
    return OpenAICompatLLM(base_url or "https://api.deepseek.com",
                           api_key, model, timeout)
