"""Shared chatbot baseline logic for CLI and HTTP API."""
import os
from typing import Any, Generator

from src.core.llm_provider import LLMProvider
from src.core.local_provider import LocalProvider
from src.core.openai_provider import OpenAIProvider
from src.core.gemini_provider import GeminiProvider
from src.database.loader import build_system_prompt
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker

SYSTEM_PROMPT = build_system_prompt()


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Set {name} in .env")
    return value


def _resolve_local_model_path(model_name: str) -> str:
    local_path = os.getenv("LOCAL_MODEL_PATH", "").strip()
    if local_path:
        return local_path
    return os.path.join("models", f"{model_name}.gguf")


def get_llm(provider: str, *, quiet: bool = False) -> LLMProvider:
    provider = provider.lower().strip()
    model_name = _require_env("DEFAULT_MODEL")

    if provider == "local":
        model_path = _resolve_local_model_path(model_name)
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Local model not found: {model_path}. "
                "Set LOCAL_MODEL_PATH or DEFAULT_MODEL in .env, then download the GGUF file."
            )
        msg = f"Loading local model: {model_name} ({model_path})"
        if quiet:
            logger.log_event(
                "LLM_LOAD",
                {"provider": "local", "model": model_name, "path": model_path},
            )
        else:
            print(f"[local] {msg} (first run may take a few minutes)")
        return LocalProvider(model_path=model_path, model_name=model_name)

    if provider == "openai":
        api_key = _require_env("OPENAI_API_KEY")
        if api_key.startswith("your_"):
            raise ValueError("Set OPENAI_API_KEY in .env for provider openai")
        if not quiet:
            print(f"[openai] Using model: {model_name}")
        return OpenAIProvider(model_name=model_name, api_key=api_key)

    if provider in ("google", "gemini"):
        api_key = _require_env("GEMINI_API_KEY")
        if api_key.startswith("your_"):
            raise ValueError("Set GEMINI_API_KEY in .env for provider google")
        if not quiet:
            print(f"[google] Using model: {model_name}")
        return GeminiProvider(model_name=model_name, api_key=api_key)

    raise ValueError(f"Unknown provider: {provider}. Use: local | openai | google")


def get_default_provider() -> str:
    return _require_env("DEFAULT_PROVIDER")


def build_prompt(history: list[dict[str, str]], user_input: str) -> str:
    lines: list[str] = []
    for turn in history:
        lines.append(f"User: {turn['user']}\nAssistant: {turn['assistant']}")
    lines.append(f"User: {user_input}")
    return "\n".join(lines)


class ChatbotBaseline:
    def __init__(self, llm: LLMProvider):
        self.llm = llm
        self.history: list[dict[str, str]] = []

    def complete(self, user_input: str) -> dict[str, Any]:
        """Non-streaming reply for API / metrics."""
        prompt = build_prompt(self.history, user_input)
        result = self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)
        content = result["content"]
        tracker.track_request(
            result.get("provider", "unknown"),
            self.llm.model_name,
            result.get("usage", {}),
            result.get("latency_ms", 0),
        )
        logger.log_event(
            "CHATBOT_TURN",
            {
                "user": user_input,
                "assistant_preview": content[:200],
                "stream": False,
                "model": self.llm.model_name,
            },
        )
        self.history.append({"user": user_input, "assistant": content})
        return {
            "reply": content,
            "model": self.llm.model_name,
            "provider": result.get("provider"),
            "usage": result.get("usage"),
            "latency_ms": result.get("latency_ms"),
        }

    def stream_tokens(self, user_input: str) -> Generator[str, None, None]:
        """Token generator for SSE; updates history when done."""
        prompt = build_prompt(self.history, user_input)
        chunks: list[str] = []
        for token in self.llm.stream(prompt, system_prompt=SYSTEM_PROMPT):
            chunks.append(token)
            yield token
        content = "".join(chunks)
        logger.log_event(
            "CHATBOT_TURN",
            {
                "user": user_input,
                "assistant_preview": content[:200],
                "stream": True,
                "model": self.llm.model_name,
            },
        )
        self.history.append({"user": user_input, "assistant": content})

    def reply(self, user_input: str, stream: bool = True) -> str:
        """CLI: print to terminal."""
        if stream:
            print("Assistant: ", end="", flush=True)
            for token in self.stream_tokens(user_input):
                print(token, end="", flush=True)
            print()
            return self.history[-1]["assistant"]
        data = self.complete(user_input)
        print(f"Assistant: {data['reply']}")
        return data["reply"]
