import os
from typing import Optional

from openai import OpenAI
from openai import NotFoundError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "FinAgent"
    environment: str = "development"

    nvidia_api_key: Optional[str] = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "openai/gpt-oss-120b"
    nvidia_fallback_model: str = "meta/llama-3.1-70b-instruct"

    tavily_api_key: Optional[str] = None


settings = Settings()


class _FallbackCompletions:
    """Mimics `client.chat.completions` and transparently retries with the
    fallback NVIDIA model when the primary is not provisioned for the account.
    """

    def __init__(self, client: OpenAI, primary: str, fallback: Optional[str]):
        self._client = client
        self._primary = primary
        self._fallback = fallback
        self.create = self._create

    def _create(self, *, model: Optional[str] = None, **kwargs):
        candidates = [model or self._primary]
        if self._fallback and self._fallback not in candidates:
            candidates.append(self._fallback)

        last_error: Optional[Exception] = None
        for candidate in candidates:
            try:
                return self._client.chat.completions.create(model=candidate, **kwargs)
            except NotFoundError as exc:
                last_error = exc
                continue

        assert last_error is not None
        raise last_error


class FallbackLLMClient:
    """Drop-in replacement for the OpenAI client exposing the same
    `chat.completions.create(model=..., **kwargs)` surface used by agents.
    """

    def __init__(self, client: OpenAI, primary: str, fallback: Optional[str] = None):
        self._client = client
        self.chat = type(
            "Chat", (), {"completions": _FallbackCompletions(client, primary, fallback)}
        )()


def get_llm_client():
    if not settings.nvidia_api_key:
        raise ValueError(
            "NVIDIA_API_KEY is not configured. Set it in .env or as an environment variable."
        )
    env_model = os.getenv("NVIDIA_MODEL")
    primary = env_model or settings.nvidia_model
    fallback = os.getenv("NVIDIA_FALLBACK_MODEL") or settings.nvidia_fallback_model
    client = OpenAI(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        timeout=60.0,
    )
    return FallbackLLMClient(client, primary=primary, fallback=fallback or None)
