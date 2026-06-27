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
            role = ""
            adapter = ""
            task_count = 0
            try:
                tasks = self.store.list_tasks(j.id)
                task_count = len(tasks)
                if tasks:
                    for t in tasks:
                        if getattr(t, "role", ""):
                            role = t.role
                            break
                    if not role:
                        role = getattr(tasks[0], "role", "")
                    for t in tasks:
                        if getattr(t, "adapter", ""):
                            adapter = t.adapter
                            break
                    if not adapter:
                        adapter = getattr(tasks[0], "adapter", "")
            except Exception:
                pass
            role = getattr(j, "role", None) or role
            adapter = getattr(j, "adapter", None) or adapter
            out.append({
                "id": j.id,
                "goal": getattr(j, "goal", ""),
                "status": str(getattr(j, "status", "")),
                "artifacts": arts,
                "created_at": getattr(j, "created_at", None),
                "role": role,
                "adapter": adapter,
                "task_count": task_count,
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
                "model": payload.get("model") or payload.get("model_chosen") or payload.get("driver"),
                "est_cost_usd": payload.get("estimated_cost_usd") or payload.get("nominal_cost_usd"),
                "role": payload.get("role") or payload.get("worker_role"),
                "rejected": payload.get("rejected"),
                "detail": payload.get("reason") or payload.get("detail"),
            })
        return out

    def events_since(self, job_id: str, cursor: int = 0) -> dict:
        try:
            events = self.store.read_events_since(job_id, cursor)
            new_cursor = self.store.event_cursor(job_id)
        except Exception:
            events, new_cursor = [], cursor
        return {"events": events, "cursor": new_cursor}
