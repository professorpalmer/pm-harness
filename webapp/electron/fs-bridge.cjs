// Native filesystem bridge for the file-explorer pane. Adapted from the Hermes
// Agent desktop fs-read-dir.cjs pattern (MIT, Nous Research): read a directory
// into a tree node list, ignoring heavy/noise dirs. Read-only.
const fs = require("node:fs");
const path = require("node:path");

const IGNORE = new Set([".git", "node_modules", ".venv", "venv", "__pycache__",
  ".codegraph", "dist", ".vite", ".DS_Store", ".pytest_cache", ".ruff_cache"]);

function registerFsBridge(ipcMain) {
  ipcMain.handle("fs:readDir", (_e, dir) => {
    try {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      const nodes = entries
        .filter((d) => !IGNORE.has(d.name))
        .map((d) => ({
          name: d.name,
          path: path.join(dir, d.name),
          dir: d.isDirectory(),
        }))
        .sort((a, b) => (a.dir === b.dir ? a.name.localeCompare(b.name) : a.dir ? -1 : 1));
      return { ok: true, nodes };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  });

  ipcMain.handle("fs:readFile", (_e, file) => {
    try {
      const stat = fs.statSync(file);
      if (stat.size > 2_000_000) return { ok: false, error: "file too large" };
      return { ok: true, content: fs.readFileSync(file, "utf8") };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  });
}

module.exports = { registerFsBridge };
