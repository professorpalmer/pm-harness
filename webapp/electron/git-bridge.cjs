// Native git bridge for the source-control pane. Adapted from the Hermes Agent
// desktop git-scm.cjs pattern (MIT, Nous Research): shell out to git for status,
// diff, and branch list. Read-only operations.
const { execFile } = require("node:child_process");

function git(repo, args) {
  return new Promise((resolve) => {
    execFile("git", ["-C", repo, ...args], { maxBuffer: 10_000_000 }, (err, stdout, stderr) => {
      if (err) return resolve({ ok: false, error: stderr || String(err) });
      resolve({ ok: true, out: stdout });
    });
  });
}

function registerGitBridge(ipcMain) {
  ipcMain.handle("git:status", async (_e, repo) => {
    const r = await git(repo, ["status", "--porcelain=v1", "-b"]);
    if (!r.ok) return r;
    const lines = r.out.split("\n").filter(Boolean);
    let branch = "";
    const files = [];
    for (const line of lines) {
      if (line.startsWith("## ")) { branch = line.slice(3).split("...")[0]; continue; }
      files.push({ status: line.slice(0, 2).trim(), path: line.slice(3) });
    }
    return { ok: true, branch, files };
  });

  ipcMain.handle("git:diff", async (_e, repo, file) => {
    const args = ["diff", "--no-color"];
    if (file) args.push("--", file);
    return git(repo, args);
  });

  ipcMain.handle("git:branches", async (_e, repo) => {
    const r = await git(repo, ["branch", "--format=%(refname:short)\t%(HEAD)"]);
    if (!r.ok) return r;
    const branches = r.out.split("\n").filter(Boolean).map((l) => {
      const [name, head] = l.split("\t");
      return { name, active: head === "*" };
    });
    return { ok: true, branches };
  });
}

module.exports = { registerGitBridge };
