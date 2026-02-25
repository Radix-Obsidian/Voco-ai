"""Token budget guard — prevents context-window overflow.

Uses ``litellm.token_counter()`` to count tokens before sending messages
to the model.  If the total exceeds ``max_tokens``, the oldest
non-protected messages are trimmed.

Protected messages (never trimmed):
  - System prompt (always first)
  - Last 4 tool result messages
  - Last 10 conversation messages
"""

from __future__ import annotations

import logging
from typing import Sequence

from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage

logger = logging.getLogger(__name__)

_DEFAULT_MAX_TOKENS = 160_000
_KEEP_LAST_TOOL_MSGS = 4
_KEEP_LAST_CONV_MSGS = 10


def _count_tokens(model: str, messages: list[dict]) -> int:
    """Count tokens using litellm, with a graceful fallback."""
    try:
        import litellm
        return litellm.token_counter(model=model, messages=messages)
    except Exception as exc:
        logger.debug("[TokenGuard] litellm.token_counter failed: %s — using char estimate", exc)
        # Rough fallback: ~4 chars per token
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        return total_chars // 4


def _msg_to_dict(msg: BaseMessage) -> dict:
    """Convert a LangChain message to a dict suitable for litellm."""
    role = "user"
    if isinstance(msg, SystemMessage):
        role = "system"
    elif hasattr(msg, "type"):
        type_map = {"human": "user", "ai": "assistant", "system": "system", "tool": "tool"}
        role = type_map.get(msg.type, "user")
    return {"role": role, "content": str(msg.content)}


def trim_messages_to_budget(
    system_prompt: str,
    messages: Sequence[BaseMessage],
    model: str = "claude-sonnet-4-5-20250929",
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> list[BaseMessage]:
    """Trim *messages* so that the total token count stays under *max_tokens*.

    Strategy:
      1. Always keep the system prompt.
      2. Protect the last ``_KEEP_LAST_TOOL_MSGS`` ToolMessages.
      3. Protect the last ``_KEEP_LAST_CONV_MSGS`` conversation messages.
      4. Trim from the oldest non-protected messages first.

    Returns the (possibly shortened) message list.
    """
    all_msgs = list(messages)

    # Build the full token-countable list including system prompt
    system_dict = {"role": "system", "content": system_prompt}
    msg_dicts = [system_dict] + [_msg_to_dict(m) for m in all_msgs]
    total_tokens = _count_tokens(model, msg_dicts)

    if total_tokens <= max_tokens:
        return all_msgs

    # Identify protected indices (0-indexed into all_msgs)
    protected: set[int] = set()

    # Protect last N conversation messages
    protected.update(range(max(0, len(all_msgs) - _KEEP_LAST_CONV_MSGS), len(all_msgs)))

    # Protect last N tool messages
    tool_indices = [i for i, m in enumerate(all_msgs) if isinstance(m, ToolMessage)]
    protected.update(tool_indices[-_KEEP_LAST_TOOL_MSGS:])

    # Trim oldest non-protected messages until we fit
    trimmable = [i for i in range(len(all_msgs)) if i not in protected]
    trimmed_count = 0
    removed: set[int] = set()

    for idx in trimmable:
        if total_tokens <= max_tokens:
            break
        msg_tokens = _count_tokens(model, [_msg_to_dict(all_msgs[idx])])
        total_tokens -= msg_tokens
        removed.add(idx)
        trimmed_count += 1

    result = [m for i, m in enumerate(all_msgs) if i not in removed]

    if trimmed_count > 0:
        logger.warning(
            "[TokenGuard] Trimmed %d messages (%d → %d tokens)",
            trimmed_count,
            _count_tokens(model, [system_dict] + [_msg_to_dict(m) for m in messages]),
            total_tokens,
        )

    return result
