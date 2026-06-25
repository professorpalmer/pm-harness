from __future__ import annotations

"""Skill distiller: the self-learning brain. Turns a completed investigation
(objective + the findings/decisions the pilot produced) into a candidate skill,
saved as PENDING for human approval.

Design discipline (stated in the roadmap): auto-generated skills that are wrong
are WORSE than none. So:
  - candidates are always PENDING (never auto-active);
  - a dedup guard skips proposing when a near-duplicate skill already exists;
  - distillation only fires when there's real signal (>= MIN_FINDINGS).

The distiller asks a model for a tight {name, description, body} envelope. Body
is a numbered, reusable procedure -- not a transcript dump.
"""

import json
import re
from dataclasses import dataclass
from typing import List, Optional

from .skill_store import SkillStore, Skill, _slug

MIN_FINDINGS = 2

DISTILL_SYSTEM = (
    "You distill a completed investigation into a REUSABLE skill: a procedure a "
    "future agent can follow for similar tasks. Output ONE JSON object only, no "
    "prose around it:\n"
    '{"name": "<short imperative title>", "description": "<one line: when to use '
    'this>", "body": "<numbered, concrete steps; include exact commands/paths/'
    'pitfalls discovered; no narrative, no transcript>"}\n'
    "If there is no durable, reusable lesson here, output {\"name\": \"\"} to skip."
)


@dataclass
class Candidate:
    name: str
    description: str
    body: str


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9]{3,}", (text or "").lower()))


def _is_duplicate(cand: Candidate, store: SkillStore, threshold: float = 0.6) -> Optional[str]:
    """Jaccard overlap on name+description tokens vs existing skills."""
    ctoks = _tokens(cand.name + " " + cand.description)
    if not ctoks:
        return None
    for sk in store.list():
        stoks = _tokens(sk.name + " " + sk.description)
        if not stoks:
            continue
        inter = len(ctoks & stoks)
        union = len(ctoks | stoks)
        if union and inter / union >= threshold:
            return sk.slug
    return None


def _escape_ctrl_in_strings(s: str) -> str:
    """Escape raw newlines/tabs that appear inside JSON string literals so a
    lenient model envelope still parses."""
    out = []
    in_str = False
    esc = False
    for ch in s:
        if esc:
            out.append(ch); esc = False; continue
        if ch == "\\":
            out.append(ch); esc = True; continue
        if ch == '"':
            in_str = not in_str; out.append(ch); continue
        if in_str and ch == "\n":
            out.append("\\n"); continue
        if in_str and ch == "\t":
            out.append("\\t"); continue
        if in_str and ch == "\r":
            out.append("\\r"); continue
        out.append(ch)
    return "".join(out)


def _parse_envelope(text: str) -> Optional[Candidate]:
    # find the first {...} JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    raw = text[start:end + 1]
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        # models often emit literal newlines/tabs inside JSON string values,
        # which strict JSON rejects. Escape control chars inside strings and retry.
        try:
            obj = json.loads(_escape_ctrl_in_strings(raw))
        except json.JSONDecodeError:
            return None
    name = (obj.get("name") or "").strip()
    if not name:
        return None
    return Candidate(
        name=name,
        description=(obj.get("description") or "").strip(),
        body=(obj.get("body") or "").strip(),
    )


def distill_session(pilot, objective: str, findings: List[dict],
                    store: SkillStore, source: str = "distilled:session") -> dict:
    """Propose a PENDING candidate skill from a finished investigation.

    Returns a status dict: {status: skipped|duplicate|proposed, slug?, reason?}.
    `pilot` is any object with .complete(prompt, system=...) -> obj with .text.
    """
    if len([f for f in findings if f.get("type") != "verification"]) < MIN_FINDINGS:
        return {"status": "skipped", "reason": "insufficient findings"}

    digest = "\n".join(
        f"- [{f.get('type','finding')}] {f.get('headline','')}"
        for f in findings if f.get("type") != "verification")
    prompt = (f"Objective: {objective}\n\nWhat was learned (findings/decisions):\n"
              f"{digest}\n\nDistill the reusable skill now.")

    resp = pilot.complete(prompt, system=DISTILL_SYSTEM)
    cand = _parse_envelope(getattr(resp, "text", "") or "")
    if not cand:
        return {"status": "skipped", "reason": "no reusable lesson"}

    dup = _is_duplicate(cand, store)
    if dup:
        return {"status": "duplicate", "slug": dup}

    skill = Skill(name=cand.name, description=cand.description, body=cand.body,
                  state="pending", source=source)
    store.save(skill)
    return {"status": "proposed", "slug": skill.slug, "name": skill.name}
