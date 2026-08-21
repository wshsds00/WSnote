import logging
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
    if not config.llm_api_key:
        logger.warning("无 LLM key：问答将降级为仅检索")
        return OpenAICompatLLM("", "", config.llm_model)  # available()=False
    return OpenAICompatLLM(config.llm_base_url or "https://api.deepseek.com",
                           config.llm_api_key, config.llm_model, config.llm_timeout)
