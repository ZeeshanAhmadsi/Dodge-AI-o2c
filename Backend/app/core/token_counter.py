import logging
import tiktoken
from typing import Optional, List, Dict, Any, Union

logger = logging.getLogger(__name__)

# --- Encoding Registry ---
# We cache encodings to avoid repeated lookups.
_ENCODING_CACHE: Dict[str, Any] = {}

# Mapping common model prefixes to their respective tiktoken encodings.
# GPT-4o and GPT-4o-mini use o200k_base.
# GPT-4 and GPT-3.5 families use cl100k_base.
MODEL_PREFIX_TO_ENCODING = {
    # OpenAI
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-4": "cl100k_base",
    "gpt-3.5": "cl100k_base",
    "text-embedding-3": "cl100k_base",
    # Groq (bare Llama model names)
    "llama-3": "cl100k_base",
    "llama": "cl100k_base",
    "gemma": "cl100k_base",
    "mixtral": "cl100k_base",
    # NVIDIA NIM models (slash-prefixed org/model format)
    "meta/": "cl100k_base",       # meta/llama-3.1-405b-instruct, etc.
    "nvidia/": "cl100k_base",     # nvidia/llama-3.1-nemotron-70b-instruct
    "mistralai/": "cl100k_base",  # mistralai/mistral-7b-instruct served via NVIDIA
    "google/": "cl100k_base",     # google/gemma served via NVIDIA
    "microsoft/": "cl100k_base",  # microsoft/phi served via NVIDIA
    # Swiftex / HuggingFace style (org/model)
    "qwen": "cl100k_base",        # Qwen family (also common on Swiftex)
    "meta-llama/": "cl100k_base", # meta-llama/Llama-3.1-8B-Instruct
}

def get_encoding_for_model(model_name: str) -> Any:
    """Retrieves the appropriate tiktoken encoding for a given model."""
    model_name = model_name.lower()
    
    # 1. Check mapping
    encoding_name = None
    for prefix, enc in MODEL_PREFIX_TO_ENCODING.items():
        if model_name.startswith(prefix):
            encoding_name = enc
            break
            
    if not encoding_name:
        logger.info("Unknown model '%s' - falling back to cl100k_base for token estimation.", model_name)
        encoding_name = "cl100k_base"
            
    # 2. Load from cache or tiktoken
    if encoding_name not in _ENCODING_CACHE:
        try:
            # Special case for newer models if they are not explicitly in prefix map
            if "gpt-4o" in model_name:
                encoding_name = "o200k_base"
            
            _ENCODING_CACHE[encoding_name] = tiktoken.get_encoding(encoding_name)
        except Exception as e:
            logger.warning("Failed to load tiktoken encoding '%s': %s. Falling back to cl100k_base.", encoding_name, e)
            if "cl100k_base" not in _ENCODING_CACHE:
                _ENCODING_CACHE["cl100k_base"] = tiktoken.get_encoding("cl100k_base")
            return _ENCODING_CACHE["cl100k_base"]
            
    return _ENCODING_CACHE[encoding_name]

def get_token_count(text: str, model: str = "gpt-4") -> int:
    """
    Highly optimized utility for fast string token counting.
    Supports model-specific encodings.
    """
    if not text:
        return 0
        
    try:
        encoding = get_encoding_for_model(model)
        # disallowed_special=() prevents Tiktoken from intentionally raising an Error
        # if the text happens to contain a reserved special token string (e.g. <|endoftext|>)
        return len(encoding.encode(str(text), disallowed_special=()))
    except Exception as e:
        logger.debug("Failed to encode text for token tracking (model=%s): %s", model, e)
        return 0

def get_chat_token_count(messages: List[Union[Dict, Any]], model: str = "gpt-4") -> int:
    """
    Accurately estimate tokens for a list of chat messages.
    Includes overhead for message formatting (role, content, etc).
    """
    # Standard OpenAI chat overhead: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
    # These constants change slightly between model families.
    if "gpt-3.5-turbo-0301" in model:
        tokens_per_message = 4
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif "gpt-4o" in model:
        # GPT-4o family: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
        tokens_per_message = 3
        tokens_per_name = 1
    elif "gpt" in model or "llama" in model:
        tokens_per_message = 3
        tokens_per_name = 1
    else:
        # Default fallback
        tokens_per_message = 3
        tokens_per_name = 1
    
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        
        content = ""
        name = None
        
        if isinstance(message, dict):
            content = message.get("content") or ""
            name = message.get("name")
            # Handle structured tool calls in dict format
            if "tool_calls" in message:
                content += str(message["tool_calls"])
        else:
            # Handle LangChain Message objects
            content = getattr(message, "content", "")
            name = getattr(message, "name", None)
            # Handle tool calls in dynamic objects
            if hasattr(message, "additional_kwargs") and "tool_calls" in message.additional_kwargs:
                content += str(message.additional_kwargs["tool_calls"])
            elif hasattr(message, "tool_calls") and message.tool_calls:
                content += str(message.tool_calls)
            
        num_tokens += get_token_count(str(content), model=model)
        if name:
            num_tokens += tokens_per_name
            
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens
