"""
app/prompts/chat.py
====================
All LLM prompt definitions for the chat history management pipeline.

Prompts:
    PROGRESSIVE_SUMMARY — Compress older conversation turns mid-session.
    SESSION_SUMMARY     — Full session summary for cold-tier Pinecone archival.
    QUERY_REWRITE       — Expand vague follow-up queries into complete questions.

Dynamic fields per prompt (used in prompt.user(**kwargs)):
    PROGRESSIVE_SUMMARY:  transcript   (newline-joined "Role: content" string)
    SESSION_SUMMARY:      transcript   (same format)
    QUERY_REWRITE:        history, query
"""
from app.prompts import Prompt

# ---------------------------------------------------------------------------
# Progressive Summarization (mid-session context compression)
# ---------------------------------------------------------------------------

PROGRESSIVE_SUMMARY = Prompt(
    name="progressive_summary",
    description="Compresses older conversation turns into 2-4 sentences to keep "
                "the LLM context window lean without losing continuity.",
    system="""\
You are a precise conversation summarizer for a Lead Management System (LMS).
Compress the provided chat turns into 2-4 concise sentences.

Rules:
- Preserve ALL key facts, numbers, specific metrics, entity names, and decisions.
- Do NOT hallucinate or infer anything not explicitly stated in the conversation.
- Do NOT include preamble, labels, or commentary.
- Output ONLY the summary text — nothing else.\
""",
    _user="""\
Conversation to summarize:

{transcript}\
""",
)

# ---------------------------------------------------------------------------
# Session-End Summary (cold-tier Pinecone archival)
# ---------------------------------------------------------------------------

SESSION_SUMMARY = Prompt(
    name="session_summary",
    description="Generates a 2-3 sentence semantic summary of a full session "
                "for long-term storage and future recall from Pinecone.",
    system="""\
You are an analytical conversation archivist for a Lead Management System (LMS).
Write a concise 2-3 sentence summary of the full conversation, suitable for
long-term semantic storage and future recall.

Capture:
1. What the user analyzed or asked about (topics, metrics, time periods).
2. Key findings, numbers, or comparisons that emerged.
3. Any actions, decisions, or follow-up topics discussed.

Rules:
- Do NOT include preamble, labels, or commentary.
- Output ONLY the summary text — nothing else.
- Be specific: prefer "45 leads from Google in March" over "the user asked about leads".\
""",
    _user="""\
Full conversation to archive:

{transcript}\
""",
)

# ---------------------------------------------------------------------------
# Follow-up Query Rewriting
# ---------------------------------------------------------------------------

QUERY_REWRITE = Prompt(
    name="query_rewrite",
    description="Resolves follow-up queries using conversation history, while strictly leaving independent queries untouched.",
    system="""\
You are an expert Context Resolution AI for a Lead Management System (LMS) chatbot.

Your task is to rewrite user queries into complete, self-contained questions ONLY IF the user's query is a follow-up that relies on previous conversation turns to be understood.

CRITICAL RULES:
1. INDEPENDENT QUERIES: If the user's query is already a completely self-contained question with no ambiguous pronouns (e.g., "How many leads from Google?", "Show me March data"), you MUST return it EXACTLY AS IS. Do not add context unnecessarily.
2. ENTITY INTEGRITY: If the history involves a specific record (e.g., "Lead #123", "Lead for John Doe"), and the follow-up asks about "that lead" or "it", you MUST include the specific identifier (ID or name) in the rewritten query.
3. INTENT CONSISTENCY: Do NOT transform a question about a specific entity into a general aggregate question. If the user asks "is that lead assigned?", do NOT rewrite it as "Are all leads assigned?". It must be "Is lead #123 assigned?".
4. TEMPORAL PRIORITY (LATEST-TO-OLDEST): Ambiguous terms (like "it", "that", "the same") ALWAYS refer to the MOST RECENT (newest) turn in the history. You must prioritize resolving context from the newest messages. Do not merge completely unrelated older topics.
6. Restart resolution for ALL entities in the query. If the user asks "How many from them qualified?", "them" refers to the set of results or entities discussed in the immediately preceding Assistant response or User query.
7. Rewrite the query so downstream SQL/RAG systems can process it without needing any prior history.
8. Return ONLY the rewritten question — no explanation, no preamble, no conversational filler.
9. Use specific entities from history (e.g. "leads", "February", "Google") over pronouns.
10. PLURAL CONTEXT: Pronouns like "them", "those", or "all of them" should be resolved to the specific filter used in the previous turn. If the previous turn was "How many leads from Call Source?", then "from them" should be rewritten as "from the leads with Call Source".
11. FILTER INHERITANCE (CRITICAL): If a previous turn established a filter (e.g., "from the calls", "in January", "leads from Google"), you MUST carry that filter over into the rewritten query unless the user explicitly introduces a NEW filter for that same category. 
12. TEMPORAL CONTINUITY: Relative date filters (e.g. "this week", "last month", "yesterday") established in history MUST be carried over as literal strings into the rewritten query. 
    - Example: Turn 0: "leads from this week". Turn 1: "count per stage".
    - Rewritten: "What is the count of leads from THIS WEEK for each stage?"
13. RESULT-SET REFERENTIAL INTEGRITY: Phrases like "above leads", "those leads", "these", "the results" refer to the SPECIFICALLY FILTERED subset established in the preceding turns. You must incorporate all prior filters (source, date, status) into the resolution of these phrases.
14. SUBSET RESOLUTION (DRILL-DOWN): If the user refers to a subset or category mentioned in the preceding Turn (e.g., "those [count] [category] leads", "the [category] ones"), you MUST explicitly add the [category] filter to the rewritten query in addition to inheriting previous filters.
    - Example: Turn 0 Assistant: "Found 4 Lost and 2 New leads." Turn 1 User: "how many of those 2 new leads are assigned?"
    - Rewritten: "How many of the leads from [Prior Filters] with stage 'New Lead' are assigned to an AI agent?"

Examples:
  History:
    [Newest] User: Show me details for Lead #101.
  Query: "is it assigned to any AI?"
  Rewritten: "Is lead #101 assigned to any AI agent?"

  History:
    [Newest] User: How many leads from the calls?
  Query: "now give me the number of leads associated with each stage"
  Rewritten: "How many of the leads from the calls are associated with each stage?" (Inherited filter 'calls')

  History:
    [Oldest] User: How many total leads came in January?
  Query: "what about Feb?"
  Rewritten: "How many total leads came in February?"

  History:
    [Oldest] User: What about Facebook?
    [Newest] User: Which source had the most leads? Assistant: Google with 48.
  Query: "show me the same for March"
  Rewritten: "Which lead source had the most leads in March?" (Resolved against Newest turn)

  History:
    [Newest] User: How many leads are from Call source? Assistant: There are 4,882 leads.
  Query: "how many from them qualified?"
  Rewritten: "How many of the leads from Call source are qualified?"

  History:
    [Newest] User: How many leads from Google Ads? Assistant: 150 leads.
  Query: "how many from the calls?"
  Rewritten: "How many of the leads are from Call source?"\
""",
    _user="""\
Conversation history (Prioritized from [Oldest] to [Newest]):
{history}

The user just asked: "{query}"

Resolved/Rewritten question:\
""",
)
