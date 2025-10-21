"""LLM integration layer with retry, backoff, and provider fallback."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, Protocol

import httpx

from config import get_settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Base error for LLM providers."""


class ProviderNotConfigured(LLMError):
    """Raised when a provider cannot be used due to missing configuration."""


class ProviderProtocol(Protocol):
    """Protocol implemented by LLM providers."""

    name: str

    def generate(self, prompt: str, **kwargs: object) -> "LLMResult":
        ...


@dataclass
class LLMResult:
    """Normalised LLM response."""

    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost: float
    provider: str


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


class OpenAIProvider:
    """HTTP-based OpenAI completion provider."""

    name = "openai"

    def __init__(self, api_key: str, timeout: float) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.model = "gpt-4o-mini"
        self.client = httpx.Client(timeout=timeout)

    def generate(self, prompt: str, **kwargs: object) -> LLMResult:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [
                {"role": "system", "content": kwargs.get("system", "You are a helpful assistant.")},
                {"role": "user", "content": prompt},
            ],
        }
        response = self.client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        if response.status_code >= 400:
            raise LLMError(f"OpenAI error: {response.text}")
        data = response.json()
        message = data["choices"][0]["message"]["content"].strip()
        prompt_tokens = data.get("usage", {}).get("prompt_tokens", _estimate_tokens(prompt))
        completion_tokens = data.get("usage", {}).get("completion_tokens", _estimate_tokens(message))
        total_tokens = prompt_tokens + completion_tokens
        cost = total_tokens * 0.000002
        return LLMResult(
            content=message,
            model=data.get("model", payload["model"]),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
            provider=self.name,
        )


class OllamaProvider:
    """HTTP client for Ollama local models."""

    name = "ollama"

    def __init__(self, host: str, timeout: float) -> None:
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.model = "llama3"
        self.client = httpx.Client(timeout=timeout)

    def generate(self, prompt: str, **kwargs: object) -> LLMResult:
        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [
                {"role": "system", "content": kwargs.get("system", "You are a helpful assistant.")},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }
        response = self.client.post(f"{self.host}/api/chat", json=payload)
        if response.status_code >= 400:
            raise LLMError(f"Ollama error: {response.text}")
        data = response.json()
        message = data.get("message", {}).get("content", "").strip()
        prompt_tokens = _estimate_tokens(prompt)
        completion_tokens = _estimate_tokens(message)
        total_tokens = prompt_tokens + completion_tokens
        cost = total_tokens * 0.000001
        return LLMResult(
            content=message or "",
            model=payload["model"],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
            provider=self.name,
        )


class OfflineProvider:
    """Deterministic fallback provider for offline environments."""

    name = "offline"

    def generate(self, prompt: str, **kwargs: object) -> LLMResult:
        snippet = prompt[:400]
        content = (
            "[offline-response]\n"
            "This environment is running in offline mode. The following prompt was received:\n"
            f"{snippet}"
        )
        tokens = _estimate_tokens(content)
        return LLMResult(
            content=content,
            model="offline-synthesiser",
            prompt_tokens=_estimate_tokens(prompt),
            completion_tokens=tokens,
            cost=0.0,
            provider=self.name,
        )


class LLMClient:
    """High level client orchestrating provider selection and retries."""

    def __init__(self, providers: Iterable[ProviderProtocol] | None = None) -> None:
        settings = get_settings()
        configured: List[ProviderProtocol] = []
        if providers:
            configured.extend(providers)
        else:
            if settings.openai_api_key:
                configured.append(OpenAIProvider(settings.openai_api_key, settings.llm_timeout))
            if settings.ollama_host:
                configured.append(OllamaProvider(settings.ollama_host, settings.llm_timeout))
        configured.append(OfflineProvider())

        self.providers = configured
        self.primary_name = settings.llm_primary
        self.max_retries = settings.llm_max_retries
        self.circuit_breaker_threshold = settings.llm_circuit_breaker_threshold
        self.failure_count = 0

    def _ordered_providers(self) -> List[ProviderProtocol]:
        primary = [p for p in self.providers if p.name == self.primary_name]
        fallback = [p for p in self.providers if p.name != self.primary_name]
        return primary + fallback

    def _handle_failure(self, error: Exception) -> None:
        self.failure_count += 1
        logger.warning("LLM provider failure", exc_info=error)
        if self.failure_count >= self.circuit_breaker_threshold:
            logger.error("LLM circuit breaker activated", extra={"failures": self.failure_count})
            raise LLMError("Circuit breaker triggered due to consecutive failures") from error

    def _reset_failures(self) -> None:
        self.failure_count = 0

    def generate(self, prompt: str, **kwargs: object) -> LLMResult:
        """Generate content using providers with retry and fallback."""

        last_error: Optional[Exception] = None
        for provider in self._ordered_providers():
            for attempt in range(1, self.max_retries + 1):
                try:
                    result = self._retryable_call(provider, prompt, **kwargs)
                    self._reset_failures()
                    logger.info(
                        "llm_success",
                        extra={
                            "provider": provider.name,
                            "model": result.model,
                            "prompt_tokens": result.prompt_tokens,
                            "completion_tokens": result.completion_tokens,
                        },
                    )
                    return result
                except ProviderNotConfigured as error:
                    last_error = error
                    break
                except Exception as error:  # pragma: no cover - fallback path
                    last_error = error
                    logger.warning(
                        "LLM attempt failed", extra={"provider": provider.name, "attempt": attempt}
                    )
                    time.sleep(2**attempt)
                    continue
        if last_error:
            self._handle_failure(last_error)
            raise last_error
        raise LLMError("No LLM providers are configured")

    def _retryable_call(self, provider: ProviderProtocol, prompt: str, **kwargs: object) -> LLMResult:
        if isinstance(provider, OpenAIProvider) and not provider.api_key:
            raise ProviderNotConfigured("OpenAI provider requires an API key")
        if isinstance(provider, OllamaProvider) and not provider.host:
            raise ProviderNotConfigured("Ollama provider requires a host")
        return provider.generate(prompt, **kwargs)

__all__ = [
    "LLMClient",
    "LLMResult",
    "LLMError",
    "OpenAIProvider",
    "OllamaProvider",
    "OfflineProvider",
]
