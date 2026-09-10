from abc import ABC, abstractmethod

import httpx
from fastapi import HTTPException

from .config import Settings


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        raise NotImplementedError


class GeminiProvider(LLMProvider):
    """Minimal Gemini REST provider; callers remain independent of Gemini's API shape."""

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model

    async def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise HTTPException(status_code=503, detail="Gemini is not configured. Set GEMINI_API_KEY, then retry.")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers={"x-goog-api-key": self.api_key}, json={"contents": [{"parts": [{"text": prompt}]}]})
            response.raise_for_status()
            candidates = response.json().get("candidates", [])
            text = candidates[0]["content"]["parts"][0]["text"] if candidates else None
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Gemini returned no text content")
            return text
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                models = await self.available_models()
                if models:
                    raise HTTPException(status_code=502, detail=f"Gemini model '{self.model}' is unavailable to this API key. Set GEMINI_MODEL to one of: {', '.join(models[:12])}") from exc
            raise HTTPException(status_code=502, detail=f"Gemini generation failed: HTTP {exc.response.status_code}.") from exc
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=f"Gemini generation failed: {exc}") from exc

    async def available_models(self) -> list[str]:
        if not self.api_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get("https://generativelanguage.googleapis.com/v1beta/models", headers={"x-goog-api-key": self.api_key})
            response.raise_for_status()
            models = response.json().get("models", [])
            supported = [model["name"].removeprefix("models/") for model in models if "generateContent" in model.get("supportedGenerationMethods", [])]
            return supported or [model["name"].removeprefix("models/") for model in models if isinstance(model.get("name"), str)]
        except (httpx.HTTPError, KeyError, TypeError):
            return []

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            await self.generate("Reply with the word ready.")
            return True
        except HTTPException:
            return False


class UnconfiguredProvider(LLMProvider):
    def __init__(self, name: str) -> None:
        self.name = name

    async def generate(self, prompt: str) -> str:
        raise HTTPException(status_code=503, detail=f"{self.name} provider is connector-ready but not configured in this MVP.")

    async def health_check(self) -> bool:
        return False


class ModelGateway:
    def __init__(self, settings: Settings) -> None:
        self.providers: dict[str, LLMProvider] = {
            "gemini": GeminiProvider(settings),
            "openai": UnconfiguredProvider("OpenAI"),
            "anthropic": UnconfiguredProvider("Anthropic"),
            "ollama": UnconfiguredProvider("Ollama"),
        }

    def provider(self, name: str) -> LLMProvider:
        provider = self.providers.get(name)
        if not provider:
            raise HTTPException(status_code=400, detail=f"Unknown model provider: {name}")
        return provider

    async def available_models(self, name: str) -> list[str]:
        provider = self.provider(name)
        if isinstance(provider, GeminiProvider):
            return await provider.available_models()
        return []
