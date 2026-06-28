"""Command execution policy: timeout resolution + danger classification.

PM-free and pure so it unit-tests fast and hermetically (AGENTS.md: the intent/
policy layer stays execution-free). Two responsibilities:

1. resolve_timeout(): how long a shell command may run. Hermes lets you turn
   timeouts off; we mirror that via HARNESS_COMMAND_TIMEOUT (seconds; 0 or
   "none"/"off" => unbounded). Default stays 120s so a fresh full-auto session
   cannot launch an unbounded remote command out of the box.

2. classify_command(): screen a shell command for irreversible or remote-reaching
   operations BEFORE execution. In full-auto (unattended) mode the harness pauses
   on a DANGER verdict and requires human approval -- the safety Hermes gets from
   its interactive destructive-op confirmation, which an autonomous loop otherwise
   lacks. In interactive co-working the human already sees every command, so the
   guard only bites in auto-mode.

The classifier is intentionally conservative: it flags by PATTERN, accepts that it
will sometimes flag a benign command (a false positive costs one approval click),
and never tries to "sanitize" or rewrite a command -- it only labels it.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

DEFAULT_TIMEOUT = 120


def resolve_timeout(env: dict | None = None) -> int | None:
    """Return the per-command timeout in seconds, or None for unbounded.

    HARNESS_COMMAND_TIMEOUT: integer seconds. 0, "none", "off", "" -> unbounded
    means the operator explicitly opted out. Unset -> DEFAULT_TIMEOUT.
    A malformed value falls back to the default (fail safe, not fail open).
    """
    env = env if env is not None else os.environ
    raw = (env.get("HARNESS_COMMAND_TIMEOUT", "") or "").strip().lower()
    if raw == "":
        return DEFAULT_TIMEOUT
    if raw in ("0", "none", "off", "unbounded", "infinite"):
        return None
    try:
        val = int(raw)
    except ValueError:
        return DEFAULT_TIMEOUT
    if val <= 0:
        return None
    return val


@dataclass
class CommandVerdict:
    danger: bool
    category: str   # "" when safe; else a short reason category
    reason: str     # human-readable explanation
    matched: str    # the pattern fragment that tripped it (for the UI)


# Each rule: (category, human reason, compiled regex). Ordered most-severe first.
# Patterns are matched case-insensitively against the raw command string.
_RULES = [
    ("destructive-recursive-delete",
     "recursive force delete",
     r"\brm\s+(-[a-z]*\s+)*-[a-z]*r[a-z]*f|\brm\s+(-[a-z]*\s+)*-[a-z]*f[a-z]*r|\brm\s+-[rf]{2}\b"),
    ("disk-write",
     "raw disk / filesystem write",
     r"\b(dd|mkfs|fdisk|parted|wipefs)\b|>\s*/dev/(sd|nvme|disk|rdisk)"),
    ("device-redirect",
     "redirect to a device or critical path",
     r">\s*/dev/(?!null|stdout|stderr)|>\s*/etc/|>\s*/boot/"),
    ("remote-shell",
     "remote machine access (ssh/scp/rsync to a host)",
     r"\bssh\s+[^\s]|\bscp\s+|\brsync\s+[^\n]*@[^\s]*:|\brsync\s+[^\n]*::|\bsftp\s+"),
    ("pipe-to-shell",
     "download piped directly into a shell",
     r"(curl|wget|fetch)\b[^|]*\|\s*(sudo\s+)?(ba|z|k|c|fi|da)?sh\b"),
    ("force-push",
     "history-rewriting git push",
     r"\bgit\s+push\b[^\n]*(--force(?!-with-lease)|\s-f\b)"),
    ("privilege-escalation",
     "privilege escalation",
     r"\bsudo\b|\bsu\s+-|\bdoas\b"),
    ("system-control",
     "service / power state change",
     r"\b(shutdown|reboot|halt|poweroff)\b|\bsystemctl\s+(stop|disable|mask)\b|\bkillall\b"),
    ("ownership-perms",
     "broad ownership or permission change",
     r"\bchmod\s+(-[a-z]*\s+)*-R\b|\bchown\s+(-[a-z]*\s+)*-R\b|\bchmod\s+777\b"),
    ("fork-bomb",
     "fork bomb",
     r":\(\)\s*\{\s*:\|:&\s*\}\s*;"),
    ("secret-exfil",
     "reading credential / key material",
     r"(cat|less|more|head|tail|cp|scp)\s+[^\n]*(\.ssh/|id_rsa|id_ed25519|\.env\b|\.aws/credentials|\.pem\b)"),
]

_COMPILED = [(cat, reason, re.compile(pat, re.IGNORECASE)) for cat, reason, pat in _RULES]


def classify_command(command: str) -> CommandVerdict:
    """Classify a shell command. Returns a CommandVerdict; danger=True means the
    command matches an irreversible/remote/escalating pattern and should be gated
    in full-auto mode. Never raises."""
    cmd = (command or "").strip()
    if not cmd:
        return CommandVerdict(False, "", "", "")
    for cat, reason, rx in _COMPILED:
        m = rx.search(cmd)
        if m:
            return CommandVerdict(True, cat, reason, m.group(0)[:80])
    return CommandVerdict(False, "", "", "")
