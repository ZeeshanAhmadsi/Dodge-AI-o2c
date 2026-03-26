import os
from dotenv import load_dotenv
from app.core import constants as C

# Load environment variables from .env file
load_dotenv()

class Settings:
    def __init__(self):
        # ── Embedding ──────────────────────────────────────────────────────
        self.HUGGINGFACE_API_KEY       = os.getenv("HUGGINGFACE_API_KEY")
        self.EMBEDDING_MODEL           = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.CHUNK_SIZE                = int(os.getenv("CHUNK_SIZE",   str(C.DEFAULT_CHUNK_SIZE)))
        self.CHUNK_OVERLAP             = int(os.getenv("CHUNK_OVERLAP", str(C.DEFAULT_CHUNK_OVERLAP)))

        # ── API Keys ───────────────────────────────────────────────────────
        self.GEMINI_API_KEY            = os.getenv("GEMINI_API_KEY")
        self.GROQ_API_KEY              = os.getenv("GROQ_API_KEY")
        self.NVIDIA_API_KEY            = os.getenv("NVIDIA_API_KEY", "")

        # ── Pinecone ───────────────────────────────────────────────────────
        self.PINECONE_API_KEY                = os.getenv("PINECONE_API_KEY")
        self.PINECONE_INDEX_NAME             = os.getenv("PINECONE_INDEX_NAME", "rag-index")
        self.PINECONE_DATA_NAMESPACE         = os.getenv("PINECONE_DATA_NAMESPACE", "leads")
        self.ANALYTICAL_QUESTIONS_NAMESPACE  = os.getenv("ANALYTICAL_QUESTIONS_NAMESPACE", "lead-management-questions")
        self.SEMANTIC_CACHE_NAMESPACE        = os.getenv("SEMANTIC_CACHE_NAMESPACE",        "semantic-cache")
        self.SEMANTIC_CACHE_THRESHOLD        = float(os.getenv("SEMANTIC_CACHE_THRESHOLD",   str(C.SEMANTIC_CACHE_THRESHOLD)))
        self.SEMANTIC_CACHE_TTL              = int(os.getenv("SEMANTIC_CACHE_TTL",            str(C.SEMANTIC_CACHE_TTL_SECONDS)))

        # ── LLM Provider Switch ───────────────────────────────────────────────
        # Options: "groq" | "swiftex" | "nvidia"
        self.LLM_PROVIDER         = os.getenv("LLM_PROVIDER", "groq").lower()

        # ── Swiftex Local LLM (used when LLM_PROVIDER=swiftex) ────────────────
        self.SWIFTEX_LLM_BASE_URL = os.getenv("SWIFTEX_LLM_BASE_URL", "https://llm.swiftex.app/v1")
        self.SWIFTEX_LLM_API_KEY  = os.getenv("SWIFTEX_LLM_API_KEY", "")
        self.SWIFTEX_LLM_MODEL    = os.getenv("SWIFTEX_LLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")

        # ── NVIDIA NIM LLM (used when LLM_PROVIDER=nvidia) ───────────────────
        self.NVIDIA_LLM_MODEL     = os.getenv("NVIDIA_LLM_MODEL", "meta/llama-3.1-405b-instruct")

        # ── LLM ──────────────────────────────────────────────────────────
        self.LLM_MODEL_NAME             = os.getenv("LLM_MODEL_NAME",            "llama-3.3-70b-versatile")
        self.LLM_VALIDATION_MODEL_NAME  = os.getenv("LLM_VALIDATION_MODEL_NAME", "llama-3.3-70b-versatile")
        self.LLM_GENERATION_TEMPERATURE = float(os.getenv("LLM_GENERATION_TEMPERATURE", str(C.DEFAULT_LLM_GENERATION_TEMPERATURE)))
        self.LLM_VALIDATION_TEMPERATURE = float(os.getenv("LLM_VALIDATION_TEMPERATURE", str(C.DEFAULT_LLM_VALIDATION_TEMPERATURE)))
        self.LLM_MIN_ANSWER_LENGTH      = int(os.getenv("LLM_MIN_ANSWER_LENGTH",    str(C.DEFAULT_LLM_MIN_ANSWER_LENGTH)))
        self.LLM_MAX_RETRIES            = int(os.getenv("LLM_MAX_RETRIES",          str(C.DEFAULT_LLM_MAX_RETRIES)))
        self.LLM_VALIDATION_THRESHOLD   = int(os.getenv("LLM_VALIDATION_THRESHOLD", str(C.DEFAULT_LLM_VALIDATION_THRESHOLD)))
        self.LLM_FALLBACK_STRATEGY      = os.getenv("LLM_FALLBACK_STRATEGY", "static_message")
        self.LLM_TIMEOUT                = float(os.getenv("LLM_TIMEOUT", "150.0"))

        # ── PostgreSQL ────────────────────────────────────────────────────
        self.DB_HOST     = os.getenv("DB_HOST",     "localhost")
        self.DB_PORT     = int(os.getenv("DB_PORT", "5432"))
        self.DB_NAME     = os.getenv("DB_NAME",     "postgres")
        self.DB_USER     = os.getenv("DB_USER",     "postgres")
        self.DB_PASSWORD = os.getenv("DB_PASSWORD", "")

        # Pool size — overridable per environment (prod may need more connections)
        self.DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", str(C.DEFAULT_DB_POOL_MIN)))
        self.DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", str(C.DEFAULT_DB_POOL_MAX)))
        self.DB_SCHEMA   = os.getenv("DB_SCHEMA",   "public")

        # ── Redis (Hot-Tier Cache) ───────────────────────────────────────────
        self.REDIS_URL             = os.getenv("REDIS_URL",          "redis://localhost:6379")
        self.REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))
        self.REDIS_SOCKET_TIMEOUT  = int(os.getenv("REDIS_SOCKET_TIMEOUT",  "5"))   # seconds

        # ── Large Dataset / Export ─────────────────────────────────────────
        # Max tokens of raw result JSON before switching to export mode.
        # Calibrated for Qwen2.5-7B (~8k context). Override via .env.
        self.LLM_RESULT_TOKEN_LIMIT = int(
            os.getenv("LLM_RESULT_TOKEN_LIMIT", str(C.LLM_RESULT_TOKEN_LIMIT))
        )

    def get_active_model_name(self) -> str:
        """
        Return the model name actually in use for the active LLM_PROVIDER.
        Single source of truth — use this everywhere you need the model name
        for token counting, logging, or fallback estimation.

        groq   → LLM_MODEL_NAME          (e.g. "llama-3.3-70b-versatile")
        swiftex → SWIFTEX_LLM_MODEL      (e.g. "meta-llama/Llama-3.1-8B-Instruct")
        nvidia  → NVIDIA_LLM_MODEL       (e.g. "meta/llama-3.1-405b-instruct")
        """
        if self.LLM_PROVIDER == "swiftex":
            return self.SWIFTEX_LLM_MODEL
        if self.LLM_PROVIDER == "nvidia":
            return self.NVIDIA_LLM_MODEL
        return self.LLM_MODEL_NAME  # groq (default)

settings = Settings()
