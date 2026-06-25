from __future__ import annotations

"""DurableState: a clean read layer over Puppetmaster's SwarmStore. This is the
data the GUI renders -- jobs, artifacts, and the live event stream. Read-only;
the Session does the writing by driving the Orchestrator.
"""

from typing import Any, Optional

from puppetmaster.store_factory import create_store


class DurableState:
    def __init__(self, state_dir: str, backend: str = "sqlite") -> None:
        self.state_dir = state_dir
        self.store = create_store(backend, state_dir)

    def list_jobs(self) -> list:
        jobs = self.store.list_jobs()
        out = []
        for j in jobs:
            arts = self.store.count_artifacts(j.id)
            out.append({
                "id": j.id,
                "goal": getattr(j, "goal", ""),
                "status": str(getattr(j, "status", "")),
                "artifacts": arts,
                "created_at": getattr(j, "created_at", None),
            })
        return out

    def job_artifacts(self, job_id: str) -> list:
        out = []
        for a in self.store.list_artifacts(job_id):
            payload = getattr(a, "payload", {}) or {}
            headline = (payload.get("claim") or payload.get("decision")
                        or payload.get("risk") or payload.get("check")
                        or payload.get("summary") or payload.get("change") or "")
            out.append({
                "id": getattr(a, "id", ""),
                "type": str(getattr(a, "type", "")),
                "headline": str(headline)[:300],
                "confidence": getattr(a, "confidence", None),
                "created_by": getattr(a, "created_by", ""),
            })
        return out

    def events_since(self, job_id: str, cursor: int = 0) -> dict:
        try:
            events = self.store.read_events_since(job_id, cursor)
            new_cursor = self.store.event_cursor(job_id)
        except Exception:
            events, new_cursor = [], cursor
        return {"events": events, "cursor": new_cursor}
