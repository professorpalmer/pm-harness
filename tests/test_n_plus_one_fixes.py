"""Regression tests for N+1 -> batch fixes: checkpoint commit-existence uses a
single git batch-check, and state.list_jobs batches task/count lookups."""
import os
import subprocess
import tempfile

from harness.checkpoints import CheckpointStore


def _git_repo_with_commit():
    repo = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-q", repo], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.email", "t@t.co"], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.name", "t"], check=True)
    with open(os.path.join(repo, "f.txt"), "w") as f:
        f.write("x")
    subprocess.run(["git", "-C", repo, "add", "-A"], check=True)
    subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "c1"], check=True)
    sha = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    return repo, sha


def test_filter_existing_commits_batch():
    repo, sha = _git_repo_with_commit()
    cs = CheckpointStore(repo)
    cs._enabled = True
    raw = [{"id": sha}, {"id": "deadbeef" * 5}, {"id": sha}]
    valid = cs._filter_existing_commits(raw)
    # Real commits kept (incl. the duplicate), the fake id dropped.
    assert len(valid) == 2
    assert all(c["id"] == sha for c in valid)


def test_filter_existing_commits_empty():
    repo, _ = _git_repo_with_commit()
    cs = CheckpointStore(repo)
    cs._enabled = True
    assert cs._filter_existing_commits([]) == []


def test_filter_existing_commits_single_spawn(monkeypatch):
    """The batch filter must spawn git AT MOST ONCE regardless of input size
    (the whole point of killing the per-checkpoint N+1)."""
    repo, sha = _git_repo_with_commit()
    cs = CheckpointStore(repo)
    cs._enabled = True

    calls = {"n": 0}
    real_run = subprocess.run

    def counting_run(*a, **k):
        calls["n"] += 1
        return real_run(*a, **k)

    monkeypatch.setattr(subprocess, "run", counting_run)
    raw = [{"id": sha} for _ in range(25)]
    cs._filter_existing_commits(raw)
    assert calls["n"] == 1  # ONE spawn for 25 checkpoints, not 25


def test_state_list_jobs_uses_batch(monkeypatch):
    """state.list_jobs must prefer the bulk task fetch over per-job list_tasks."""
    from harness import state as state_mod

    class FakeTask:
        def __init__(self, job_id, role="impl", adapter="local"):
            self.job_id = job_id
            self.role = role
            self.adapter = adapter

    class FakeJob:
        def __init__(self, jid):
            self.id = jid
            self.goal = "g"
            self.status = "done"
            self.created_at = 0

    class FakeStore:
        def __init__(self):
            self.per_job_calls = 0
            self.bulk_calls = 0
        def list_jobs(self):
            return [FakeJob("j1"), FakeJob("j2")]
        def list_tasks(self, jid):
            self.per_job_calls += 1
            return [FakeTask(jid)]
        def list_tasks_for_jobs(self, jids):
            self.bulk_calls += 1
            return [FakeTask(j) for j in jids]
        def count_artifacts_for_jobs(self, jids):
            return {j: 3 for j in jids}
        def count_artifacts(self, jid):
            self.per_job_calls += 1
            return 3

    ds = state_mod.DurableState.__new__(state_mod.DurableState)
    ds.store = FakeStore()
    jobs = ds.list_jobs()
    assert len(jobs) == 2
    assert ds.store.bulk_calls == 1      # one bulk task fetch
    assert ds.store.per_job_calls == 0   # no per-job task/count queries
    assert all(j["artifacts"] == 3 and j["task_count"] == 1 for j in jobs)
