"""
app/core/constants.py
======================
Application-wide constants that do NOT change between environments.

RULE:
  env-dependent   (API keys, URLs, host, model names, passwords) → .env + config.py
  code defaults   (algorithm tuning, business rules, security)   → constants.py

config.py reads .env values and falls back to these constants as defaults.
To tune a default: change it ONCE here and it propagates everywhere.
"""


# ─────────────────────────────────────────────────────────────────────────────
# RAG / Vector Search
# ─────────────────────────────────────────────────────────────────────────────

# Number of context chunks to retrieve from Pinecone for answer generation
RAG_CONTEXT_TOP_K: int = 10

# Number of template chunks to retrieve from Pinecone for prompt building
RAG_TEMPLATE_TOP_K: int = 1

# Minimum cosine similarity score to accept a RAG classification match.
# Below this threshold the query defaults to "reasoning" type.
CLASSIFICATION_SIMILARITY_THRESHOLD: float = 0.5

# Minimum cosine similarity score to accept a Semantic Cache hit.
# High threshold (0.95-0.98) ensures accuracy for enterprise data.
SEMANTIC_CACHE_THRESHOLD: float = 0.96

# Redis TTL for semantic cache entries (7 days in seconds)
SEMANTIC_CACHE_TTL_SECONDS: int = 604_800


# ─────────────────────────────────────────────────────────────────────────────
# Chunking Defaults
# ─────────────────────────────────────────────────────────────────────────────

# Default text chunk size (in characters) for RAG ingestion
DEFAULT_CHUNK_SIZE: int = 1000

# Default overlap between consecutive chunks
DEFAULT_CHUNK_OVERLAP: int = 150


# ─────────────────────────────────────────────────────────────────────────────
# LLM Pipeline Defaults  (overridable via .env)
# ─────────────────────────────────────────────────────────────────────────────

# Minimum answer length the deterministic validator requires
DEFAULT_LLM_MIN_ANSWER_LENGTH: int = 20

# Maximum LLM generation retry attempts before triggering fallback
DEFAULT_LLM_MAX_RETRIES: int = 1

# Minimum score (1–10) the LLM validator must assign for an answer to pass
DEFAULT_LLM_VALIDATION_THRESHOLD: int = 7

# Default generation temperature
DEFAULT_LLM_GENERATION_TEMPERATURE: float = 0.7

# Default validation temperature (deterministic — always 0)
DEFAULT_LLM_VALIDATION_TEMPERATURE: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Embedding Service
# ─────────────────────────────────────────────────────────────────────────────

# Number of documents to embed in a single batch (avoids memory/API timeouts)
EMBEDDING_BATCH_SIZE: int = 50

# Number of retry attempts for a failed embedding batch before raising
EMBEDDING_MAX_RETRIES: int = 3


# ─────────────────────────────────────────────────────────────────────────────
# Database / Connection Pool  (overridable via .env)
# ─────────────────────────────────────────────────────────────────────────────

# Default minimum warm connections (production may set DB_POOL_MIN higher)
DEFAULT_DB_POOL_MIN: int = 2

# Default maximum simultaneous connections (production may set DB_POOL_MAX higher)
DEFAULT_DB_POOL_MAX: int = 10

# Maximum rows a query may return before the user is asked to use aggregation
DB_QUERY_RESULT_LIMIT: int = 100


# ─────────────────────────────────────────────────────────────────────────────
# SQL Security
# ─────────────────────────────────────────────────────────────────────────────

# SQL keywords that are never allowed in an analytical query (defence in depth
# alongside the LLM-based verifier)
FORBIDDEN_SQL_KEYWORDS: list = [
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "EXEC",
    "EXECUTE",
    "CALL",
    "COPY",
    "pg_sleep",
    "pg_read_file",
    "pg_write_file",
    "information_schema",
    "pg_catalog",
    "UNION",
]

# Regex patterns to detect SQL injection tricks
FORBIDDEN_SQL_PATTERNS: list = [
    r"--",           # inline comment
    r"/\*",          # block comment start
    r"\*/",          # block comment end
    r";.+",          # query stacking (anything after semicolon)
    r"\bOR\s+1\s*=\s*1\b",  # generic boolean injection
]


# ───────────────────────────────────────────────────────────────────────────────
# Chat History  (Three-Tier Memory)
# ───────────────────────────────────────────────────────────────────────────────

# Redis TTL for hot-tier cache (24 hours in seconds)
HISTORY_HOT_TTL_SECONDS: int = 86_400

# Max messages stored in the hot Redis cache per session
HISTORY_HOT_MAX_MESSAGES: int = 20

# Sliding window sizes per flow type injected into LLM context
HISTORY_ANALYTICAL_WINDOW: int = 4   # last N turns for analytical queries
HISTORY_REASONING_WINDOW: int = 6    # last N turns for reasoning queries
HISTORY_FOLLOWUP_WINDOW: int = 8     # expanded when follow-up is detected

# When session history exceeds this length, progressive summarization kicks in
HISTORY_SUMMARIZE_THRESHOLD: int = 12

# Words that signal a follow-up query requiring more context
FOLLOW_UP_SIGNALS: list = [
    "that", "it", "those", "them", "this", "same",
    "again", "before", "last", "earlier", "previous",
    "above", "mentioned", "as i said", "what about",
]

# Pinecone namespace pattern for cold (semantic) memory
# Formatted as: COLD_MEMORY_NAMESPACE.format(org_id=..., user_id=...)
COLD_MEMORY_NAMESPACE: str = "chat-memory:{org_id}:{user_id}"

# Redis key pattern for hot session cache
# Formatted as: REDIS_SESSION_KEY.format(session_key=...)
REDIS_SESSION_KEY: str = "chat:history:{session_key}"

# Redis key pattern for compressed session summary (pre-cold-storage)
REDIS_SUMMARY_KEY: str = "chat:summary:{session_key}"

# ───────────────────────────────────────────────────────────────────────────────
# Agentic Analytics Config
# ───────────────────────────────────────────────────────────────────────────────

# Maximum times the PlanExecutor will ask the Planner for a patch plan on failure
MAX_REPLAN_ATTEMPTS: int = 5


# ───────────────────────────────────────────────────────────────────────────────
# Large Dataset / Export
# ───────────────────────────────────────────────────────────────────────────────

# Number of result-JSON tokens above which we switch to the export path.
# Calibrated for the local Qwen2.5-7B model (~8k context window).
# Override via LLM_RESULT_TOKEN_LIMIT in .env.
LLM_RESULT_TOKEN_LIMIT: int = 4_000

# How long a pending export job survives in Redis (seconds, 15 minutes).
# After this window the user can no longer Accept the export.
EXPORT_REDIS_TTL_SECONDS: int = 900

# How long a generated Excel file is kept on disk before auto-deletion.
EXPORT_FILE_TTL_SECONDS: int = 900

# Redis key templates for the export sub-system
REDIS_EXPORT_JOB_KEY: str = "export:job:{export_id}"
REDIS_EXPORT_FILE_KEY: str = "export:file:{export_id}"
