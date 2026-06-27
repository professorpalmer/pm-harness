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
                    store: SkillStore, source: str = "distilled:session",
                    extra_context: str = "") -> dict:
    """Propose a PENDING candidate skill from a finished investigation.

    Returns a status dict: {status: skipped|duplicate|proposed|patch_proposed, slug?, reason?}.
    `pilot` is any object with .complete(prompt, system=...) -> obj with .text.
    """
    non_verification_findings = [f for f in findings if f.get("type") != "verification"]
    if len(non_verification_findings) < MIN_FINDINGS:
        if not extra_context:
            return {"status": "skipped", "reason": "insufficient findings"}
        digest = extra_context
    else:
        digest = "\n".join(
            f"- [{f.get('type','finding')}] {f.get('headline','')}"
            for f in non_verification_findings)

    prompt = (f"Objective: {objective}\n\nWhat was learned (findings/decisions):\n"
              f"{digest}\n\nDistill the reusable skill now.")

    resp = pilot.complete(prompt, system=DISTILL_SYSTEM)
    cand = _parse_envelope(getattr(resp, "text", "") or "")
    if not cand:
        return {"status": "skipped", "reason": "no reusable lesson"}

    dup = _is_duplicate(cand, store)
    if dup:
        existing = store.get(dup)
        if existing:
            merge_prompt = (
                f"We have an existing skill:\n"
                f"Name: {existing.name}\n"
                f"Description: {existing.description}\n"
                f"Body:\n{existing.body}\n\n"
                f"And a new candidate procedure from a recent session:\n"
                f"Name: {cand.name}\n"
                f"Description: {cand.description}\n"
                f"Body:\n{cand.body}\n\n"
                f"Please merge these two into a single updated, complete, and cohesive skill procedure. "
                f"Preserve all useful instructions from both. Output ONE JSON object only, matching the original format:\n"
                f'{{"name": "<imperative title>", "description": "<one line>", "body": "<merged numbered steps>"}}'
            )
            merge_resp = pilot.complete(merge_prompt, system=DISTILL_SYSTEM)
            merged_cand = _parse_envelope(getattr(merge_resp, "text", "") or "")
            if merged_cand and merged_cand.body.strip() != existing.body.strip():
                patch_skill = store.propose_update(
                    slug=dup,
                    new_body=merged_cand.body,
                    new_name=merged_cand.name,
                    new_description=merged_cand.description,
                    source=source
                )
                return {"status": "patch_proposed", "slug": patch_skill.slug, "supersedes": dup, "name": patch_skill.name}
        return {"status": "duplicate", "slug": dup}

    skill = Skill(name=cand.name, description=cand.description, body=cand.body,
                  state="pending", source=source)
    store.save(skill)
    return {"status": "proposed", "slug": skill.slug, "name": skill.name}


# ---- Rules distillation -----------------------------------------------------
from .rule_store import RuleStore, Rule

RULES_SYSTEM = (
    "You extract standing CONVENTIONS from a finished session: terse always/never "
    "constraints a future agent must honor for this project (e.g. 'never use "
    "emojis in output', 'always run tests before claiming done'). These are NOT "
    "task procedures -- they are rules. Output ONE JSON object only:\n"
    '{"rules": [{"text": "<imperative constraint>", "scope": "global"}]}\n'
    "Output {\"rules\": []} if no durable convention emerged. Max 3 rules; only "
    "genuinely reusable constraints, not task-specific notes."
)


def distill_rules(pilot, objective: str, findings: List[dict],
                  store: "RuleStore", source: str = "distilled:session",
                  corrections: Optional[List[str]] = None) -> dict:
    """Propose PENDING candidate rules from a finished session. Returns
    {status, proposed: [slugs], duplicates: [slugs]}."""
    if corrections is None:
        corrections = []

    findings_digest = "\n".join(f"- {f.get('headline','')}" for f in findings
                                if f.get("type") != "verification")

    corrections_digest = ""
    if corrections:
        corrections_digest = "User Corrections/Feedback:\n" + "\n".join(f"- {c}" for c in corrections)

    if not findings_digest.strip() and not corrections_digest.strip():
        return {"status": "skipped", "reason": "no signal"}

    digest_parts = []
    if findings_digest.strip():
        digest_parts.append(findings_digest)
    if corrections_digest.strip():
        digest_parts.append(corrections_digest)

    digest = "\n\n".join(digest_parts)

    prompt = (f"Objective: {objective}\n\nWhat happened:\n{digest}\n\n"
              f"Extract standing conventions now.")
    resp = pilot.complete(prompt, system=RULES_SYSTEM)
    text = getattr(resp, "text", "") or ""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return {"status": "skipped", "reason": "no envelope"}
    try:
        obj = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        try:
            obj = json.loads(_escape_ctrl_in_strings(text[start:end + 1]))
        except json.JSONDecodeError:
            return {"status": "skipped", "reason": "parse failed"}
    proposed, dups = [], []
    for r in (obj.get("rules") or [])[:3]:
        rtext = (r.get("text") or "").strip()
        if not rtext:
            continue
        dup = store.exists_similar(rtext)
        if dup:
            dups.append(dup); continue
        rule = Rule(text=rtext, scope=(r.get("scope") or "global").strip(),
                    state="pending", source=source)
        store.add(rule)
        proposed.append(rule.slug)
    return {"status": "proposed" if proposed else ("duplicate" if dups else "skipped"),
            "proposed": proposed, "duplicates": dups}
