import os
import logging
from dataclasses import dataclass, field
from typing import Tuple, List, Dict, Optional, Any

logger = logging.getLogger(__name__)

PERSISTED_OUTPUT_TAG = "<persisted-output>"
PERSISTED_OUTPUT_CLOSING_TAG = "</persisted-output>"


def _default_max_result() -> int:
    try:
        return int(os.environ.get("HARNESS_MAX_TOOL_RESULT_CHARS", "8000"))
    except ValueError:
        return 8000


def _default_turn_budget() -> int:
    try:
        return int(os.environ.get("HARNESS_TURN_BUDGET_CHARS", "48000"))
    except ValueError:
        return 48000


@dataclass(frozen=True)
class BudgetConfig:
    max_result_chars: int = field(default_factory=_default_max_result)
    turn_budget_chars: int = field(default_factory=_default_turn_budget)
    preview_chars: int = 1500


def generate_preview(content: str, max_chars: int = 1500) -> Tuple[str, bool]:
    """Truncate at last newline within max_chars. Returns (preview, has_more)."""
    if len(content) <= max_chars:
        return content, False
    truncated = content[:max_chars]
    last_nl = truncated.rfind("\n")
    if last_nl > max_chars // 2:
        truncated = truncated[:last_nl + 1]
    return truncated, True


def spill_to_disk(content: str, result_id: str, state_dir: str) -> str:
    """Write FULL content to {state_dir}/pmharness-results/{result_id}.txt."""
    abs_state_dir = os.path.abspath(state_dir)
    target_dir = os.path.join(abs_state_dir, "pmharness-results")
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, f"{result_id}.txt")
    with open(file_path, "w", encoding="utf-8", errors="replace") as f:
        f.write(content)
    return file_path


def build_persisted_message(
    preview: str,
    has_more: bool,
    original_size: int,
    file_path: str,
) -> str:
    """Build the <persisted-output> replacement block."""
    size_kb = original_size / 1024
    if size_kb >= 1024:
        size_str = f"{size_kb / 1024:.1f} MB"
    else:
        size_str = f"{size_kb:.1f} KB"

    msg = f"{PERSISTED_OUTPUT_TAG}\n"
    msg += f"This tool result was too large ({original_size:,} characters, {size_str}).\n"
    msg += f"Full output saved to: {file_path}\n"
    msg += "Use read_file with offset and limit to read specific sections\n\n"
    msg += f"Preview (first {len(preview)} chars):\n"
    msg += preview
    if has_more:
        msg += "\n..."
    msg += f"\n{PERSISTED_OUTPUT_CLOSING_TAG}"
    return msg


def maybe_persist_result(
    content: str,
    result_id: str,
    state_dir: str,
    config: BudgetConfig,
    threshold: Optional[int] = None,
) -> str:
    """Layer 2: persist oversized result, return preview + path. Falls back to inline truncation if write fails."""
    effective_threshold = threshold if threshold is not None else config.max_result_chars

    if len(content) <= effective_threshold:
        return content

    preview, has_more = generate_preview(content, max_chars=config.preview_chars)

    try:
        file_path = spill_to_disk(content, result_id, state_dir)
        return build_persisted_message(preview, has_more, len(content), file_path)
    except Exception as e:
        logger.warning("Spill to disk failed for %s: %s", result_id, e)
        fallback_msg = (
            f"{preview}\n\n"
            f"[Truncated: tool response was {len(content):,} chars. "
            f"Full output could not be saved: {e}]"
        )
        return fallback_msg


def enforce_turn_budget(
    tool_messages: List[Dict[str, Any]],
    state_dir: str,
    config: BudgetConfig,
) -> List[Dict[str, Any]]:
    """Layer 3: enforce aggregate budget across all tool results in a turn."""
    candidates = []
    total_size = 0
    for i, msg in enumerate(tool_messages):
        content = msg.get("content", "")
        if not isinstance(content, str):
            content = str(content) if content is not None else ""
        size = len(content)
        total_size += size
        if PERSISTED_OUTPUT_TAG not in content:
            candidates.append((i, size))

    if total_size <= config.turn_budget_chars:
        return tool_messages

    candidates.sort(key=lambda x: x[1], reverse=True)

    for idx, size in candidates:
        if total_size <= config.turn_budget_chars:
            break
        msg = tool_messages[idx]
        content = msg.get("content", "")
        if not isinstance(content, str):
            content = str(content) if content is not None else ""
        
        tc_id = msg.get("tool_call_id") or f"turn_budget_{idx}"

        replacement = maybe_persist_result(
            content=content,
            result_id=tc_id,
            state_dir=state_dir,
            config=config,
            threshold=0,
        )
        if replacement != content:
            total_size -= size
            total_size += len(replacement)
            tool_messages[idx]["content"] = replacement
            logger.info("Turn budget enforcement: persisted tool result %s (%d chars)", tc_id, size)

    return tool_messages
