"""
app/prompts/__init__.py
========================
Central prompt registry for all LLM calls in Swiftex Sense.

Usage:
    from app.prompts.analytical import SQL_GENERATION
    from app.prompts.chat import QUERY_REWRITE

    messages = SQL_GENERATION.build(page_id="PID_LEAD_PAGE", schema="...")
    response = llm.invoke(messages)

    # Or just get the rendered strings:
    system = SQL_GENERATION.system          # system has no dynamic fields
    user   = SQL_GENERATION.user(page_id=..., schema=...)  # user does
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List

from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage


@dataclass
class Prompt:
    """
    A single LLM prompt with a fixed system message and an optionally
    dynamic user message template.

    System message:
        Pure text — no dynamic fields. Describes role, rules, output format.
        Retrieved via `prompt.system`.

    User message:
        A Python format string. Dynamic fields are injected with `prompt.user(**kwargs)`.
        E.g. "Schema:\n{schema}\n\nQuestion: {query}"

    Usage:
        messages = SOME_PROMPT.build(schema="...", query="...")
        response = llm.invoke(messages)
    """
    name:        str
    description: str
    system:      str
    _user:       str = field(repr=False)         # raw template string

    def user(self, **kwargs) -> str:
        """Render the user message template with the given keyword arguments."""
        return self._user.format(**kwargs)

    def build(self, **user_kwargs) -> List[BaseMessage]:
        """
        Return a ready-to-invoke [SystemMessage, HumanMessage] list.

        Args:
            **user_kwargs: Values for every {placeholder} in the user template.

        Example:
            messages = SQL_GENERATION.build(page_id="PID_LEAD_PAGE", schema="...")
        """
        messages: List[BaseMessage] = [SystemMessage(content=self.system)]
        if self._user:
            messages.append(HumanMessage(content=self.user(**user_kwargs)))
        return messages

    def build_with_history(self, history_block: str, **user_kwargs) -> List[BaseMessage]:
        """
        Same as build() but injects a conversation history SystemMessage
        between the main system prompt and the user message.
        Use this for multi-turn analytical/reasoning calls.

        Args:
            history_block: Pre-formatted [CONVERSATION HISTORY] string.
            **user_kwargs:  Values for the user template placeholders.
        """
        messages: List[BaseMessage] = [SystemMessage(content=self.system)]
        if history_block:
            messages.append(SystemMessage(content=history_block))
        if self._user:
            messages.append(HumanMessage(content=self.user(**user_kwargs)))
        return messages
