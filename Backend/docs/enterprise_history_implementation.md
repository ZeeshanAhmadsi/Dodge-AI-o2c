# Enterprise Chat History System — Implementation Documentation

## Table of Contents
1. [What Was Built](#1-what-was-built)
2. [Architecture Overview](#2-architecture-overview)
3. [File-by-File Explanation](#3-file-by-file-explanation)
4. [Full Request Flow — Step by Step](#4-full-request-flow--step-by-step)
5. [How Each Tier Works](#5-how-each-tier-works)
6. [Smart Context Injection](#6-smart-context-injection)
7. [Reasoning History Fix](#7-reasoning-history-fix)
8. [Session Lifecycle](#8-session-lifecycle)
9. [API Reference](#9-api-reference)
10. [How to Run](#10-how-to-run)

---

## 1. What Was Built

Before this implementation, chat history was:
- Stored in a plain Python dict in RAM → **lost on every server restart**
- Ignored entirely in the reasoning flow → **LLM had no memory between turns**
- Not scoped to any user or organization → **insecure in multi-tenant environments**
- Truncated naively at 20 messages → **no intelligence in what was kept**

After this implementation, chat history is:

| Property | Before | After |
|---|---|---|
| Storage | RAM only | Redis (hot) + Postgres (warm) + Pinecone (cold) |
| Restarts | Lost | Survives (Postgres is permanent) |
| Reasoning memory | None | Full multi-turn context injected into LLM |
| Multi-tenant | Single global dict | Isolated per `org_id:user_id:page_id:chat_id` |
| Context selection | Last 20 (truncate) | Smart window by query type + follow-up detection |
| Long sessions | Truncated | Progressively summarized |
| Cross-session recall | None | Semantic search via Pinecone cold storage |
| Audit trail | None | Every message saved to Postgres with SQL, latency, tokens |

---

## 2. Architecture Overview

```
┌───────────────────────────────────────────────────────────────────┐
│                         CLIENT REQUEST                            │
│              POST /api/v1/chat/?query=...&org_id=...              │
└───────────────────────────┬───────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────────┐
│                    app/api/routes/chat.py                         │
│  1. Validate session key (org+user+page+chat composite)           │
│  2. Load history  →  Redis HIT or Postgres fallback               │
│  3. Run progressive summarization if session is long              │
│  4. Build smart context window (ContextBuilder)                   │
│  5. Recall cold memory from Pinecone (cross-session)              │
│  6. Call ChatRouter.process_query(...)                            │
│  7. Persist exchange → Redis + Postgres                           │
└───────────────────────────┬───────────────────────────────────────┘
                            │
               ┌────────────▼────────────┐
               │    ChatRouter           │
               │  (services/chat/router) │
               │                         │
               │  1. Relevance check     │
               │  2. RAG classification  │
               │     (Pinecone vector    │
               │      similarity)        │
               │  3. Dispatch            │
               └──────┬──────────┬───────┘
                      │          │
          ┌───────────▼──┐  ┌────▼──────────────────────────┐
          │  ANALYTICAL  │  │         REASONING              │
          │  FLOW        │  │  LLMOrchestratorService        │
          │              │  │  + conversation_history injected│
          │  Schema       │  │  + cold memory injected        │
          │  → SQL gen   │  │  → Template retrieval          │
          │  → SQL verify│  │  → Context retrieval           │
          │  → DB fetch  │  │  → Generation (with history)   │
          │  → LLM summ. │  │  → LLM validation (judge)      │
          │    (history  │  │  → Retry if failed             │
          │     injected)│  │  → Fallback if all retries used│
          └──────────────┘  └───────────────────────────────┘
```

### Three-Tier Memory

```
TIER 1 — HOT (Redis)
  Key:   chat:history:{org_id}:{user_id}:{page_id}:{chat_id}
  TTL:   24 hours (auto-expires inactive sessions)
  Value: JSON list of {role, content} dicts (last 20 messages)
  Use:   Every request reads from here first. Sub-millisecond.

TIER 2 — WARM (PostgreSQL)
  Tables: ChatSession, ChatMessage
  Use:    Permanent storage. Redis loads from here on cache-miss.
          Stores SQL, latency, token counts per message (audit trail).

TIER 3 — COLD (Pinecone)
  Namespace: chat-memory:{org_id}:{user_id}
  Use:    Session-end summaries stored as vector embeddings.
          Retrieved via semantic search when current query matches
          past conversation topics — gives cross-session memory.
```

---

## 3. File-by-File Explanation

### Infrastructure

#### `app/core/constants.py` — New history constants
```python
HISTORY_HOT_TTL_SECONDS   = 86_400   # Redis TTL: 24 hours
HISTORY_HOT_MAX_MESSAGES  = 20       # Max messages in Redis hot cache
HISTORY_ANALYTICAL_WINDOW = 4        # Last N turns for analytical queries
HISTORY_REASONING_WINDOW  = 6        # Last N turns for reasoning queries
HISTORY_FOLLOWUP_WINDOW   = 8        # Expanded when follow-up detected
HISTORY_SUMMARIZE_THRESHOLD = 12     # Trigger progressive summarization
FOLLOW_UP_SIGNALS         = [...]    # Words that signal a follow-up query
COLD_MEMORY_NAMESPACE     = "chat-memory:{org_id}:{user_id}"
REDIS_SESSION_KEY         = "chat:history:{session_key}"
REDIS_SUMMARY_KEY         = "chat:summary:{session_key}"
```

#### `app/core/config.py` — Redis config added
```python
self.REDIS_URL             = os.getenv("REDIS_URL", "redis://localhost:6379")
self.REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))
self.REDIS_SOCKET_TIMEOUT  = int(os.getenv("REDIS_SOCKET_TIMEOUT", "5"))
```

#### `app/db/migrations/001_create_chat_tables.sql` — Database schema
Two new tables:

**ChatSession** — one row per conversation:
```sql
id             UUID  PRIMARY KEY DEFAULT gen_random_uuid()
organizationId TEXT  NOT NULL
userId         TEXT  NOT NULL
pageId         TEXT  NOT NULL DEFAULT 'default'
chatId         TEXT  NOT NULL
createdAt      TIMESTAMPTZ
updatedAt      TIMESTAMPTZ    ← auto-updated via trigger on new messages
```
Unique index on `(organizationId, userId, pageId, chatId)` — prevents duplicate sessions.

**ChatMessage** — every message ever sent:
```sql
id          UUID  PRIMARY KEY
sessionId   UUID  FK → ChatSession(id) ON DELETE CASCADE
role        TEXT  CHECK IN ('user', 'assistant')
content     TEXT
type        TEXT  -- 'analytical' | 'reasoning' | 'out_of_scope'
sql         TEXT  -- stored for analytical queries (audit + replay)
tokensUsed  INT   -- LLM cost tracking
latencyMs   INT   -- response time
createdAt   TIMESTAMPTZ
```

A PostgreSQL trigger `ChatMessage_touch_session` automatically updates `ChatSession.updatedAt` whenever a new message is inserted.

#### `app/db/chat_repository.py` — DB operations
```python
class ChatRepository:
    get_or_create_session(org_id, user_id, page_id, chat_id) → session_id
      # INSERT ... ON CONFLICT DO UPDATE (upsert)
      # Returns UUID of the session

    save_message(session_id, role, content, type, sql, tokens, latency) → bool
      # Inserts one row into ChatMessage

    get_session_messages(session_id) → List[Dict]
      # SELECT all messages for session, ordered by createdAt ASC
      # Used when Redis cache misses

    get_session_by_composite_key(org_id, user_id, page_id, chat_id) → Dict
      # Looks up the session row to get its UUID
```
Uses the **existing psycopg2 connection pool** (`get_db_connection` / `return_db_connection`). No new DB dependencies.

---

### Service Layer

#### `app/services/chat/summarizer.py` — ConversationSummarizer

Two public methods:

**`maybe_compress(history)`** — Progressive Summarization:
- Called every request if history has grown long
- Triggers when `len(history) >= HISTORY_SUMMARIZE_THRESHOLD` (12)
- Splits history in half: old half → LLM summary string, new half → kept verbatim
- Returns `(summary_text, recent_messages)`
- The old half is **not thrown away** — it's compressed into a 2–4 sentence summary that gets prepended to the context window

**`summarize_session(history)`** — Session-End Summary:
- Called when a WebSocket disconnects or session is explicitly closed
- LLM generates a 2–3 sentence summary of the full conversation
- This summary is stored in Pinecone (cold tier)

Both use temperature=0.0 for deterministic, factual output.

---

#### `app/services/chat/context_builder.py` — ContextBuilder

**`is_follow_up(query)`**:
- Checks if query contains any `FOLLOW_UP_SIGNALS` word
- Signals: "that", "it", "those", "same", "again", "before", "last", "earlier", "previous", "above", "mentioned", "as i said", "what about"
- If true → expands the context window to 8 turns instead of the default

**`build_context(history, query, query_type, progressive_summary)`**:
- Selects the right number of turns:
  - Analytical query → last 4 turns
  - Reasoning query → last 6 turns
  - Follow-up detected → last 8 turns
- Formats into a clean human-readable block:

```
[CONVERSATION HISTORY]
Past context summary: "User analyzed Google leads in Q1..."

User: how many leads this month?
Assistant: There are 45 leads so far in March.
User: which source was highest?
Assistant: Google was highest with 18 leads.
```

This formatted block is what gets injected into the LLM prompt.

---

#### `app/services/chat/history_service.py` — HistoryService (Three-Tier Orchestrator)

This is the core of the system. It manages all three tiers.

**Redis initialization** (`init_redis()` / `close_redis()`):
- Creates a `redis.ConnectionPool` from the URL in settings
- Pool allows up to 20 simultaneous connections
- Called from `app/main.py` lifespan on startup/shutdown
- If Redis is unreachable, system degrades gracefully to Postgres-only

**`build_session_key(org_id, user_id, page_id, chat_id)`**:
- Returns `"{org_id}:{user_id}:{page_id}:{chat_id}"`
- This is the single composite identifier used in all three tiers

**`get_or_create_session(...)`**:
- Calls `ChatRepository.get_or_create_session()` to upsert in Postgres
- Returns the composite `session_key` string

**`load_history(session_key)`** — Hot → Warm fallback:
```
1. Try Redis: GET chat:history:{session_key}
   → HIT:  Deserialize JSON → return list
   → MISS: Continue to step 2

2. Parse session_key → org_id, user_id, page_id, chat_id
3. Query Postgres for session UUID
4. SELECT all messages FROM ChatMessage WHERE sessionId = ...
5. Repopulate Redis with Postgres data (SETEX with 24h TTL)
6. Return history list
```

**`save_turn(session_key, query, response, type, sql, tokens, latency)`**:
```
1. Postgres: save_message(user_turn) + save_message(assistant_turn)
2. Redis:
   a. load current history
   b. append user + assistant messages
   c. trim to last 20 if over limit
   d. SETEX with refreshed 24h TTL
```

**`close_session(session_key)`** — Cold archival:
```
1. Load full message history from Postgres (authoritative source)
2. Call ConversationSummarizer.summarize_session(history) → LLM summary
3. embed_query(summary) → 384-dim vector
4. VectorStoreService.add_vectors([vector], [metadata], namespace, [id])
   namespace = "chat-memory:{org_id}:{user_id}"
   id = "session-{session_key}"
5. Delete Redis keys for this session (hot cache eviction)
```

**`recall_cold_memory(query, org_id, user_id)`** — Cross-session recall:
```
1. embed_query(query) → vector
2. VectorStoreService.similarity_search_by_vector(
       vector, top_k=1,
       namespace="chat-memory:{org_id}:{user_id}"
   )
3. Return metadata["summary"] of best match
   → "" if nothing found or threshold not met
```

**`get/set_progressive_summary(session_key)`**:
- Caches the progressive summary text in Redis at `chat:summary:{session_key}`
- Retrieved and prepended to context on every request
- TTL matches the session hot cache (24h)

---

#### `app/services/chat/router.py` — ChatRouter (Refactored)

**Now stateless** — receives pre-built context from the caller instead of owning history.

```python
def process_query(query, context_text, cold_memory, orchestrator):
    # 1. Relevance check (QueryRelevanceService)
    # 2. RAG vector similarity → classify as analytical or reasoning
    # 3. Dispatch to _handle_analytical or _handle_reasoning
```

**`_handle_analytical(query, context_text)`**:
```
Schema → SQL Generate → SQL Verify → DB Fetch → Handle Result → LLM Summary
                                                                      ↑
                                          context_text injected here as SystemMessage
```

**`_handle_reasoning(query, context_text, cold_memory, orchestrator)`**:
```
Combine:
  combined_context = "[LONG-TERM MEMORY]\n{cold_memory}\n\n{context_text}"

orchestrator.process_and_generate(
    question=query,
    conversation_history=combined_context   ← NEW: injected into LLM prompt
)
```

---

### Reasoning Pipeline (Modified)

#### `app/services/reasoning/generation.py`

Added `conversation_history: str = ""` parameter to `generate_answer()`.

**Prompt construction before:**
```
{system_instruction}

{formatted_prompt}
{correction_instruction}
```

**Prompt construction after:**
```
{system_instruction}

[CONVERSATION HISTORY]
Past context summary: "..."
User: ...
Assistant: ...

{formatted_prompt}
{correction_instruction}
```

The history block is inserted between the system prompt and the actual question so:
1. The LLM first sees WHO it is and its rules
2. Then sees WHAT was discussed before
3. Then sees the CURRENT question with live data context

#### `app/services/reasoning/orchestrator.py`

Added `conversation_history: str = ""` to `process_and_generate()` and passes it straight through to `generator.generate_answer(...)`.

---

### API Layer

#### `app/api/dependencies.py`

Added:
```python
_history_service: HistoryService | None = None

def get_history_service() -> HistoryService:
    global _history_service
    if _history_service is None:
        _history_service = HistoryService()
    return _history_service
```
Lazy singleton — created on first request, reused forever.

#### `app/api/routes/chat.py` — Full per-request flow

Every `POST /api/v1/chat/` request executes this exact sequence:

```
1.  Validate query is not empty

2.  history_svc.get_or_create_session(org_id, user_id, page_id, chat_id)
    → Upserts in Postgres, returns session_key

3.  history_svc.load_history(session_key)
    → Redis HIT or Postgres fallback
    → Returns List[{role, content}]

4.  summarizer.maybe_compress(history)
    → If len >= 12: compress old half → summary_text, return recent
    → If < 12:      return ("", history) unchanged

5.  If summary_text: history_svc.set_progressive_summary(session_key, summary)
    Else:            prog_summary = history_svc.get_progressive_summary(session_key)

6.  ctx_builder.is_follow_up(query)
    → Detect pronoun / reference signals

7.  ctx_builder.build_context(history, query, "reasoning", prog_summary)
    → Select N turns based on query type + follow-up flag
    → Format as [CONVERSATION HISTORY] block
    → Returns (turns, context_text)

8.  history_svc.recall_cold_memory(query, org_id, user_id)
    → embed query → Pinecone similarity search in user's namespace
    → Returns matching past session summary or ""

9.  start_ms = time.time() * 1000

10. chat_router.process_query(query, context_text, cold_memory, orchestrator)
    → Relevance check → classify → dispatch → return result

11. latency_ms = time.time()*1000 - start_ms

12. If result.status == "success":
      history_svc.save_turn(session_key, query, response, type, sql, latency_ms)
      → Postgres: INSERT user + assistant messages
      → Redis:    Append + trim + SETEX

13. Return JSON response:
    {
      session_key, status, type, response,
      sql, data_preview, latency_ms, is_follow_up
    }
```

**WebSocket** (`WS /api/v1/chat/ws/{session_key}`)  
Same steps 3–13 on every received message.  
On `WebSocketDisconnect` → calls `history_svc.close_session(session_key)` which:
- Loads full history from Postgres
- LLM generates session summary
- Embeds + upserts to Pinecone cold namespace
- Deletes Redis keys

#### `app/main.py` — Startup/Shutdown

```python
async def lifespan(app):
    # STARTUP
    init_db_pool()   # Postgres pool: min=2, max=10 connections
    init_redis()     # Redis pool: max=20 connections, ping verified
    yield
    # SHUTDOWN
    close_redis()    # Graceful pool close
    close_db_pool()  # Return all connections
```

---

## 4. Full Request Flow — Step by Step

### Example: User sends "how many leads this month?"

```
Client: POST /api/v1/chat/?query=how many leads this month?
        &org_id=acme&user_id=john&page_id=leads&chat_id=abc-123

─────────────────────────────────────────────────────────────
ROUTES/CHAT.PY
─────────────────────────────────────────────────────────────
① session_key = "acme:john:leads:abc-123"

② load_history("acme:john:leads:abc-123")
   → Redis key = "chat:history:acme:john:leads:abc-123"
   → MISS (first request)
   → Postgres: SELECT messages for sessionId
   → Returns [] (new session)
   → Redis: SETEX [] TTL=86400

③ maybe_compress([]) → ("", [])   # empty, nothing to compress

④ is_follow_up("how many leads this month?") → False

⑤ build_context([], query, "reasoning", "")
   → window=6, turns=[], formatted=""

⑥ recall_cold_memory("how many leads...", "acme", "john")
   → Pinecone search in namespace "chat-memory:acme:john"
   → No past sessions → returns ""

⑦ chat_router.process_query(
       query="how many leads this month?",
       context_text="",
       cold_memory="",
       orchestrator=<LLMOrchestratorService>
   )

─────────────────────────────────────────────────────────────
CHATROUTER
─────────────────────────────────────────────────────────────
⑧ relevance_service.check_relevance(query)
   → Groq LLM: is this LMS-related? → is_relevant=True

⑨ embedder.embed_query("how many leads this month?")
   → 384-dim vector

⑩ vector_store.similarity_search_by_vector(
       vector, top_k=1, namespace="lead-management-questions"
   )
   → Best match score=0.87 ≥ threshold=0.5
   → metadata.type = "analytical"
   → query_type = "ANALYTICAL"

⑪ _handle_analytical("how many leads this month?", context_text="")

─────────────────────────────────────────────────────────────
ANALYTICAL FLOW
─────────────────────────────────────────────────────────────
⑫ _get_page_schema("PID_LEAD_PAGE")
   → Reads app/data/schema.json[PID_LEAD_PAGE]
   → Returns table structure + column definitions

⑬ _generate_sql("PID_LEAD_PAGE", schema, query)
   → Groq LLM: generate SQL for "how many leads this month?"
   → Returns: SELECT COUNT(*) FROM "Lead"
              WHERE EXTRACT(MONTH FROM "createdAt") = EXTRACT(MONTH FROM NOW())
              AND   EXTRACT(YEAR  FROM "createdAt") = EXTRACT(YEAR  FROM NOW())

⑭ _verify_sql(sql, schema)
   → Groq LLM: is this SQL valid and safe?
   → {"is_valid": true, "reason": "..."}

⑮ _fetch_from_db(sql)
   → Executes SQL against Postgres
   → Returns JSON: [{"count": 45}]

⑯ _handle_result_set(data_json)
   → Small result → pass through

⑰ LLM summarization:
   messages = [
     SystemMessage("You are an LMS analyst..."),
     HumanMessage("User asked: how many leads...\nData: [{'count': 45}]")
   ]
   → "There are 45 leads so far this month."

─────────────────────────────────────────────────────────────
BACK IN ROUTES
─────────────────────────────────────────────────────────────
⑱ latency_ms = 2340ms

⑲ save_turn(
       session_key="acme:john:leads:abc-123",
       query="how many leads this month?",
       response="There are 45 leads so far this month.",
       query_type="analytical",
       sql="SELECT COUNT(*)...",
       latency_ms=2340
   )
   → Postgres: INSERT user message, INSERT assistant message
   → Redis: [
       {role:user, content:"how many leads this month?"},
       {role:assistant, content:"There are 45 leads so far this month."}
     ] → SETEX TTL=86400

⑳ Return:
   {
     "session_key": "acme:john:leads:abc-123",
     "status": "success",
     "type": "analytical",
     "response": "There are 45 leads so far this month.",
     "sql": "SELECT COUNT(*) FROM \"Lead\" WHERE ...",
     "data_preview": "[{\"count\": 45}]",
     "latency_ms": 2340,
     "is_follow_up": false
   }
```

### Example: Follow-up "which source was highest?"

```
① load_history → Redis HIT → [user: "how many...", assistant: "45 leads..."]
② maybe_compress([2 msgs]) → below threshold, no change
③ is_follow_up("which source was highest?") → True ("highest" not a signal,
   but next query "same as last time?" → "same" IS a signal)
④ build_context → window=4 (analytical), turns = last 4 = [both messages]
⑤ context_text = """
   [CONVERSATION HISTORY]
   User: how many leads this month?
   Assistant: There are 45 leads so far this month.
   """
⑥ classified analytical → _handle_analytical(query, context_text)
⑦ LLM summarization step now sees context_text as SystemMessage
   → LLM understands "which source" refers to the lead sources already discussed
```

---

## 5. How Each Tier Works

### Tier 1 — Redis (Hot)

```python
# Write (save_turn)
r.setex(
    "chat:history:acme:john:leads:abc-123",
    86400,                          # TTL: 24 hours
    json.dumps([                    # Serialized message list
        {"role": "user",      "content": "..."},
        {"role": "assistant", "content": "..."},
    ])
)

# Read (load_history)
raw = r.get("chat:history:acme:john:leads:abc-123")
history = json.loads(raw)           # Instant — sub-millisecond
```

Degrades gracefully: if Redis is down, `_redis_client` is None and all hot-tier operations are skipped silently — Postgres takes over.

### Tier 2 — Postgres (Warm)

```sql
-- Session upsert (get_or_create_session)
INSERT INTO "ChatSession" ("organizationId", "userId", "pageId", "chatId")
VALUES ('acme', 'john', 'leads', 'abc-123')
ON CONFLICT ("organizationId", "userId", "pageId", "chatId")
DO UPDATE SET "updatedAt" = NOW()
RETURNING "id";

-- Message save (save_message)
INSERT INTO "ChatMessage"
    ("sessionId", "role", "content", "type", "sql", "latencyMs")
VALUES
    ('uuid...', 'user', 'how many leads?', 'analytical', NULL, NULL),
    ('uuid...', 'assistant', 'There are 45...', 'analytical', 'SELECT...', 2340);

-- History reload (get_session_messages)
SELECT "role", "content", "type", "sql", "createdAt"
FROM "ChatMessage"
WHERE "sessionId" = 'uuid...'
ORDER BY "createdAt" ASC;
```

### Tier 3 — Pinecone (Cold)

```python
# Session end → summarize → embed → store
summary = "User analyzed lead count this month. Found 45 total leads.
           Identified Google as top source. Asked about pipeline stages."

vector = embedder.embed_query(summary)   # 384-dim float array

vector_store.add_vectors(
    vectors=[vector],
    metadatas=[{"summary": summary, "session_key": "acme:john:leads:abc-123"}],
    namespace="chat-memory:acme:john",
    ids=["session-acme:john:leads:abc-123"]
)

# New session, new query → recall
query_vec = embedder.embed_query("same analysis as before?")
results = vector_store.similarity_search_by_vector(
    query_vec, top_k=1, namespace="chat-memory:acme:john"
)
# Returns: {"summary": "User analyzed lead count...", score: 0.91}
```

---

## 6. Smart Context Injection

### Window Selection Logic

```python
if is_follow_up(query):
    window = 8          # expanded: follow-up needs more context
elif query_type == "analytical":
    window = 4          # SQL doesn't need much history
else:                   # reasoning
    window = 6          # conversational, needs more turns

turns = history[-window:]
```

### Progressive Summarization

When session grows to 12+ messages:
```
Before (12 messages):
  [msg1, msg2, msg3, msg4, msg5, msg6, msg7, msg8, msg9, msg10, msg11, msg12]

After compression:
  summary = "User analyzed leads, found 45 in March, Google top source..."
  recent  = [msg7, msg8, msg9, msg10, msg11, msg12]

What LLM receives:
  [CONVERSATION HISTORY]
  Past context summary: "User analyzed leads, found 45 in March..."

  User: msg7
  Assistant: msg8
  ...
  User: current query
```

The LLM gets continuity without receiving 12 full messages — saves tokens and stays within context window.

---

## 7. Reasoning History Fix

**Before:** `LLMOrchestratorService.process_and_generate(question)` — no history.

**After:** `process_and_generate(question, conversation_history="")` — history injected.

**Prompt structure after fix:**
```
[SYSTEM INSTRUCTION + RULES]
You are a helpful LMS assistant...
CRITICAL SYSTEM RULES:
- Only answer from provided context
- ...

[CONVERSATION HISTORY]                    ← NEW
Past context summary: "..."
User: previous question
Assistant: previous answer

Context:
{live RAG data retrieved from Pinecone}

Question:
{current user question}

[CORRECTION INSTRUCTION if retrying]
```

The history is placed AFTER the system rules but BEFORE the live data context so the LLM first internalizes its persona, then understands prior conversation, then sees the current data.

---

## 8. Session Lifecycle

```
User hits "New Chat"
    ↓
GET /api/v1/chat/sessions/new?org_id=X&user_id=Y&page_id=Z
    → Postgres: INSERT ChatSession (or return existing)
    → Returns: session_key = "X:Y:Z:{new_uuid}"

User sends messages
    ↓
POST /api/v1/chat/?query=...&session_key=X:Y:Z:uuid
    → Redis HIT → fast context load
    → Save to Redis + Postgres
    [... many messages ...]
    → After 12 messages: progressive summarization kicks in
    → Old turns compressed, recent kept verbatim

User closes browser (WebSocket disconnect)
    ↓
WebSocketDisconnect caught in route handler
    → history_svc.close_session(session_key)
    → Load full history from Postgres
    → LLM generates session summary
    → Embed summary → Pinecone cold namespace
    → Delete Redis keys (session over)

User returns next day, new conversation, asks about past analysis
    ↓
recall_cold_memory("same analysis...") → Pinecone search
    → Finds "User analyzed leads in March..." from yesterday's session
    → Injected as [LONG-TERM MEMORY] in prompt
    → LLM answers with context of past session
```

---

## 9. API Reference

### Create Session
```
GET /api/v1/chat/sessions/new
  ?org_id=<string>    REQUIRED
  ?user_id=<string>   REQUIRED
  ?page_id=<string>   optional (default: "default")

Response:
{
  "session_key": "org1:user1:leads:abc-123",
  "chat_id": "abc-123",
  "org_id": "org1",
  "user_id": "user1",
  "page_id": "leads"
}
```

### Send Message (REST)
```
POST /api/v1/chat/
  ?query=<string>     REQUIRED
  ?org_id=<string>    REQUIRED
  ?user_id=<string>   REQUIRED
  ?page_id=<string>   optional
  ?chat_id=<string>   optional (auto-generated if omitted)

Response:
{
  "session_key": "org1:user1:leads:abc-123",
  "status": "success",
  "type": "analytical" | "reasoning" | "out_of_scope",
  "response": "There are 45 leads...",
  "sql": "SELECT COUNT(*) FROM ...",    (analytical only)
  "data_preview": "[{...}]",           (analytical only)
  "latency_ms": 2340,
  "is_follow_up": false
}
```

### WebSocket
```
WS /api/v1/chat/ws/{session_key}

Send:  {"query": "how many leads?"}
Recv:  {"session_key": "...", "status": "success", "type": "...", "response": "..."}

On disconnect: session archived to Pinecone cold storage automatically.
```

### Get History
```
GET /api/v1/chat/history/{session_key}
Response: {"session_key": "...", "history": [...], "count": 12}
```

### Close & Archive Session
```
DELETE /api/v1/chat/history/{session_key}
→ Generates summary → Pinecone → evicts Redis
Response: {"message": "Session ... archived and closed."}
```

---

## 10. How to Run

### 1. Install redis package
```bash
venv\Scripts\pip install redis
```

### 2. Run DB migration (from swiftex-sense folder)
```bash
venv\Scripts\python -c "
from app.db.connection import init_db_pool, get_db_connection, return_db_connection
init_db_pool()
conn = get_db_connection()
cur  = conn.cursor()
sql  = open('app/db/migrations/001_create_chat_tables.sql').read()
cur.execute(sql)
conn.commit()
print('Migration OK')
"
```

### 3. Start server
```bash
venv\Scripts\python -m uvicorn app.main:app --port 8080 --reload
```

### 4. Verify startup logs
```
INFO - DB connection pool initialized → localhost:5432/postgres
INFO - Redis connection pool initialized → redis://localhost:6379
INFO - Application startup complete.
```

### 5. Test
```bash
# Create session
curl "http://localhost:8080/api/v1/chat/sessions/new?org_id=acme&user_id=john"

# Send analytical query
curl -X POST "http://localhost:8080/api/v1/chat/?query=how+many+leads+this+month&org_id=acme&user_id=john&chat_id=<chat_id_from_step_1>"

# Send reasoning query
curl -X POST "http://localhost:8080/api/v1/chat/?query=what+is+a+lead&org_id=acme&user_id=john&chat_id=<chat_id>"
```
