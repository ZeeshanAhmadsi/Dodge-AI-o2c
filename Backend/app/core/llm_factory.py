"""
app/core/llm_factory.py
========================
Enterprise-level LLM provider factory.

Controls which LLM backend is used across the entire application via a single
environment variable:

    LLM_PROVIDER=groq     → Groq Cloud  (langchain_groq.ChatGroq)
    LLM_PROVIDER=swiftex  → Swiftex local LLM (langchain_openai.ChatOpenAI
                             pointed at SWIFTEX_LLM_BASE_URL with x-api-key header)
    LLM_PROVIDER=nvidia   → NVIDIA NIM (langchain_nvidia_ai_endpoints.ChatNVIDIA
                             pointed at api.nvidia.com using NVIDIA_API_KEY)

All consumer modules call get_chat_llm() or get_structured_llm() — they never
import a provider SDK directly, keeping provider concerns fully isolated here.

Token tracking:
    Both Groq and the Swiftex endpoint return an OpenAI-compatible usage block
    (prompt_tokens / completion_tokens / total_tokens).  The token_counter.py
    tiktoken fallback covers any provider that omits usage metadata.
"""

import logging
from typing import Any, Type

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported providers
# ---------------------------------------------------------------------------
_PROVIDER_GROQ    = "groq"
_PROVIDER_SWIFTEX = "swiftex"
_PROVIDER_NVIDIA  = "nvidia"
_SUPPORTED_PROVIDERS = {_PROVIDER_GROQ, _PROVIDER_SWIFTEX, _PROVIDER_NVIDIA}


def _validate_provider(provider: str) -> None:
    """Raise early with a clear message for unsupported providers."""
    if provider not in _SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported LLM_PROVIDER: '{provider}'. "
            f"Valid options: {sorted(_SUPPORTED_PROVIDERS)}. "
            "Check your .env file."
        )


def _build_groq(model_name: str, temperature: float) -> BaseChatModel:
    """Construct a Groq-backed chat model."""
    if not settings.GROQ_API_KEY:
        raise ValueError(
            "LLM_PROVIDER=groq but GROQ_API_KEY is not set. "
            "Add it to your .env file."
        )
    from langchain_groq import ChatGroq  # lazy import to avoid cost when not used

    logger.debug(
        "[LLMFactory] Provider=groq  model=%s  temp=%s", model_name, temperature
    )
    return ChatGroq(
        model_name=model_name,
        temperature=temperature,
        groq_api_key=settings.GROQ_API_KEY,
        timeout=settings.LLM_TIMEOUT,
        max_retries=settings.LLM_MAX_RETRIES,
    )


def _build_swiftex(model_name: str, temperature: float) -> BaseChatModel:
    """
    Construct an OpenAI-SDK-compatible chat model pointing at the Swiftex
    internal LLM endpoint.

    The Swiftex API uses the header  ``x-api-key``  (not ``Authorization: Bearer``),
    so we pass the key via ``default_headers`` instead of ``api_key`` to avoid
    the SDK prepending 'Bearer '.
    """
    if not settings.SWIFTEX_LLM_API_KEY:
        raise ValueError(
            "LLM_PROVIDER=swiftex but SWIFTEX_LLM_API_KEY is not set. "
            "Add it to your .env file."
        )
    from langchain_openai import ChatOpenAI  # lazy import

    logger.debug(
        "[LLMFactory] Provider=swiftex  base_url=%s  model=%s  temp=%s",
        settings.SWIFTEX_LLM_BASE_URL,
        model_name,
        temperature,
    )
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        base_url=settings.SWIFTEX_LLM_BASE_URL,
        # Use a dummy value for api_key (SDK requires non-empty) and pass the
        # real key in the custom header that Swiftex expects.
        api_key="swiftex-local",
        default_headers={"x-api-key": settings.SWIFTEX_LLM_API_KEY},
        timeout=settings.LLM_TIMEOUT,
        max_retries=settings.LLM_MAX_RETRIES,
    )


def _build_nvidia(model_name: str, temperature: float) -> BaseChatModel:
    """
    Construct an NVIDIA NIM-backed chat model using the NVIDIA AI Endpoints SDK.

    Requires the ``langchain-nvidia-ai-endpoints`` package.
    The ``NVIDIA_API_KEY`` env var is picked up automatically by ChatNVIDIA,
    but we also pass it explicitly for clarity and to support future overrides.
    """
    if not settings.NVIDIA_API_KEY:
        raise ValueError(
            "LLM_PROVIDER=nvidia but NVIDIA_API_KEY is not set. "
            "Add it to your .env file."
        )
    from langchain_nvidia_ai_endpoints import ChatNVIDIA  # lazy import

    logger.debug(
        "[LLMFactory] Provider=nvidia  model=%s  temp=%s", model_name, temperature
    )
    return ChatNVIDIA(
        model=model_name,
        api_key=settings.NVIDIA_API_KEY,
        temperature=temperature,
        top_p=0.7,
        max_tokens=1024,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_chat_llm(
    temperature: float | None = None,
    model_name: str | None = None,
) -> BaseChatModel:
    """
    Return a configured chat LLM for the active provider.

    Args:
        temperature:  Override the generation temperature. Defaults to
                      ``settings.LLM_GENERATION_TEMPERATURE``.
        model_name:   Override the model identifier. Defaults to the
                      provider-appropriate model from settings.

    Returns:
        A LangChain ``BaseChatModel`` instance ready to be invoked.

    Provider is controlled by LLM_PROVIDER in .env (groq | swiftex | nvidia).
    """
    provider = settings.LLM_PROVIDER
    _validate_provider(provider)

    resolved_temp = temperature if temperature is not None else settings.LLM_GENERATION_TEMPERATURE

    # Force the provider-specific model; callers that blindly pass a Groq model
    # name won't accidentally break a Swiftex or NVIDIA deployment.
    if provider == _PROVIDER_SWIFTEX:
        resolved_model = settings.SWIFTEX_LLM_MODEL
    elif provider == _PROVIDER_NVIDIA:
        resolved_model = settings.NVIDIA_LLM_MODEL
    else:
        resolved_model = model_name or _default_model(provider)

    logger.info(
        "[LLMFactory] Building chat LLM — provider=%s  model=%s  temp=%s",
        provider, resolved_model, resolved_temp,
    )

    if provider == _PROVIDER_GROQ:
        return _build_groq(resolved_model, resolved_temp)
    if provider == _PROVIDER_NVIDIA:
        return _build_nvidia(resolved_model, resolved_temp)
    return _build_swiftex(resolved_model, resolved_temp)


def get_structured_llm(
    schema: Type[BaseModel],
    temperature: float | None = None,
    model_name: str | None = None,
) -> Any:
    """
    Return a chat LLM bound to a Pydantic structured-output schema.

    Equivalent to ``get_chat_llm(...).with_structured_output(schema)``.

    Args:
        schema:      A Pydantic ``BaseModel`` subclass defining the output shape.
        temperature: Override the temperature (default 0.0 for deterministic output).
        model_name:  Override the model identifier.

    Returns:
        A LangChain ``Runnable`` that yields instances of ``schema``.

    Provider is controlled by LLM_PROVIDER in .env (groq | swiftex | nvidia).
    """
    resolved_temp = temperature if temperature is not None else 0.0
    llm = get_chat_llm(temperature=resolved_temp, model_name=model_name)
    return llm.with_structured_output(schema)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _default_model(provider: str) -> str:
    """Return the settings-driven default model for the given provider."""
    if provider == _PROVIDER_GROQ:
        return settings.LLM_MODEL_NAME
    if provider == _PROVIDER_NVIDIA:
        return settings.NVIDIA_LLM_MODEL
    # swiftex
    return settings.SWIFTEX_LLM_MODEL
