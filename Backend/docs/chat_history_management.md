# Chat History Management — Swiftex Sense

## 1. Current State (What We Have Now)

```
app/api/routes/chat.py
  sessions: Dict[str, List[Dict]] = {}   ← RAM only
```

- **Storage:** Python in-memory dictionary — wiped on every server restart.
- **Session key:** Random `uuid4` — no concept of user, org, or page.
- **Max size:** Last 20 messages per session (hard truncation — old messages are lost).
- **Reasoning flow:** History is received but **silently dropped** — `LLMOrchestratorService` does not accept it.
- **Analytical flow:** Only the last 4 turns are injected into the LLM prompt.

**Verdict:** Functional for a demo. Not production-ready.

---

## 2. Enterprise Target Architecture — Three-Tier Memory Model

```
┌────────────────────────────────────────────────────────────┐
│                       USER QUERY                           │
└──────────────────────────┬─────────────────────────────────┘
                           │
           ┌───────────────▼───────────────┐
           │         TIER 1: HOT           │
           │  Redis  ·  TTL = 24 hours     │
           │  Last 10 messages (verbatim)  │
           │  Sub-millisecond reads        │
           └───────────────┬───────────────┘
                           │ (on miss or cold start)
           ┌───────────────▼───────────────┐
           │         TIER 2: WARM          │
           │  PostgreSQL (via Prisma)      │
           │  Full message history         │
           │  Persistent, per-user/org     │
           └───────────────┬───────────────┘
                           │ (for cross-session recall)
           ┌───────────────▼───────────────┐
           │         TIER 3: COLD          │
           │  Pinecone (existing index)    │
           │  Compressed session summaries │
           │  Vector search across history │
           └───────────────────────────────┘
```

---

## 3. Tier-by-Tier Explanation

### Tier 1 — Hot (Redis)

**What it stores:** The last 10 messages of an active session, verbatim.

**Why Redis:** In-memory, accessed in microseconds. Every chat message response is fast because we never touch the DB for active conversations.

**Key schema:**
```
key:   chat:history:{org_id}:{user_id}:{page_id}:{chat_id}
value: JSON list of {role, content, type, timestamp}
TTL:   24 hours (auto-expires inactive sessions)
```

**Flow:**
```
Request arrives
  → Check Redis for session key
  → HIT  → use it directly (no DB call)
  → MISS → load from Postgres → populate Redis → use it
```

---

### Tier 2 — Warm (PostgreSQL via Prisma)

**What it stores:** The full, permanent message history — every message ever sent, with metadata.

**Why Postgres:** You already have it running. Prisma schema just needs two new models.

**Proposed Prisma schema addition:**
```prisma
model ChatSession {
  id             String        @id @default(uuid())
  organizationId String
  userId         String
  pageId         String
  createdAt      DateTime      @default(now())
  updatedAt      DateTime      @updatedAt
  messages       ChatMessage[]
}

model ChatMessage {
  id          String      @id @default(uuid())
  sessionId   String
  session     ChatSession @relation(fields: [sessionId], references: [id])
  role        String      // "user" | "assistant"
  content     String
  type        String?     // "analytical" | "reasoning" | "out_of_scope"
  sql         String?     // stored for analytical queries
  tokensUsed  Int?
  latencyMs   Int?
  createdAt   DateTime    @default(now())
}
```

**Why store `sql`, `tokensUsed`, `latencyMs`:**
- `sql` → allows auditing and re-running exact queries
- `tokensUsed` → cost tracking per org/user
- `latencyMs` → performance monitoring

---

### Tier 3 — Cold (Pinecone)

**What it stores:** A compressed **summary** of each completed session, stored as a vector embedding.

**Why it's different from Tier 2:**
- Tier 2 = exact storage, retrieved by known `session_id`
- Tier 3 = semantic search, retrieved by **query similarity** when you don't know which past session is relevant

**How it works:**
```
Session ends (user disconnects / TTL expires)
  → LLM generates 2–3 sentence summary:
    "User analyzed lead sources in Q1. Found Google leads had 12% conversion.
     Compared with Facebook leads at 8%. Asked about pipeline stages."
  → Summary is embedded and stored in Pinecone
     namespace: f"chat-memory:{org_id}:{user_id}"

New session, new query: "Same analysis as last time?"
  → Embed query → search Pinecone namespace
  → Retrieves relevant past summary
  → Inject into LLM context as "Previous conversation context"
```

---

## 4. Multi-Tenant Session Key Design

The session key must encode all tenant dimensions to ensure strict data isolation:

```python
# Current (insecure for multi-tenant)
session_id = str(uuid.uuid4())

# Target
session_key = f"{org_id}:{user_id}:{page_id}:{chat_id}"

# In Redis
redis_key = f"chat:history:{session_key}"

# In Pinecone (namespace per org+user)
namespace = f"chat-memory:{org_id}:{user_id}"
```

This ensures:
- User A can never access User B's history
- Org X's data is isolated from Org Y
- Page-level context is preserved (lead page vs task page)

---

## 5. Smart Context Injection (Layer 2 Logic)

Rather than dumping all history into the LLM, inject the right amount per query type:

```python
def build_context(history: list, query: str, query_type: str) -> list:

    if query_type == "analytical":
        # SQL generation doesn't need much history
        # but follow-up detection is important
        recent = history[-4:]

    elif query_type == "reasoning":
        # Reasoning benefits from more conversational context
        # Use sliding window + summary
        if len(history) > 12:
            summary = history["compressed_summary"]   # stored separately
            recent = history[-6:]
            # inject: summary + recent 6 turns
        else:
            recent = history  # use all if short

    # Follow-up detection — force more context
    follow_up_signals = ["that", "it", "those", "same", "again", "before", "last"]
    if any(word in query.lower() for word in follow_up_signals):
        recent = history[-8:]   # expand window

    return recent
```

---

## 6. Progressive Summarization

When a session grows beyond 12 messages, instead of hard-truncating, **summarize the older half**:

```
Messages 1–8   →  LLM generates summary:
                  "User asked about lead counts by source, then pipeline stages,
                   then requested comparison between Q1 and Q2."

Messages 9–14  →  Kept verbatim (recent, precise)

What LLM sees:
  [SYSTEM] Previous context summary: "User asked about..."
  [Human]  Turn 9 message
  [AI]     Turn 10 message
  ...
  [Human]  Current query
```

This keeps the context window small while preserving long-term coherence.

---

## 7. Implementation Roadmap

| Phase | What | Impact | Effort |
|-------|------|--------|--------|
| **Phase 1** | Pass history to `LLMOrchestratorService` in reasoning flow | Fixes reasoning memory immediately | ~2 hours |
| **Phase 2** | Add `ChatSession` + `ChatMessage` Prisma models, persist every message | Survive restarts, full audit trail | ~1 day |
| **Phase 3** | Add Redis as hot-tier cache, load from Postgres on miss | Production-grade performance | ~1 day |
| **Phase 4** | Composite session keys (`org_id:user_id:page_id`) | True multi-tenant isolation | ~2 hours |
| **Phase 5** | Progressive summarization for long sessions | Smart context, lower LLM costs | ~1 day |
| **Phase 6** | Session-end summaries → Pinecone cold storage | Cross-session semantic recall | ~1 day |

**Total to full enterprise-grade: ~5 developer days** (all phases).

---

## 8. What the Final Flow Looks Like

```
User sends message
        │
        ▼
1. Build session_key (org + user + page + chat)
2. Load hot context from Redis (or warm from Postgres)
3. Detect follow-up signals → adjust context window
4. Classify query (analytical / reasoning)
        │
   ┌────┴────┐
   │         │
ANALYTICAL  REASONING
   │         │
   │         ├── Load cold memory from Pinecone (cross-session)
   │         ├── Inject: cold summary + recent turns
   │         └── LLMOrchestratorService (validate + retry + fallback)
   │
   ├── Inject last 4 turns
   └── SQL pipeline → DB → LLM summary
        │
        ▼
5. Save message to Postgres (permanent)
6. Update Redis (hot cache)
7. Return response
        │
        ▼
Session ends (disconnect / TTL)
        │
        ▼
8. Generate session summary → embed → Pinecone (cold storage)
```
