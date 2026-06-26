// Electron main process for pm-harness.
// Responsibilities:
//  1. Spawn the Python harness backend (harness.cli gui) on a loopback port.
//  2. Create the BrowserWindow loading the Vite build (or dev server).
//  3. Register IPC handlers that back the renderer's transport seam
//     (window.harnessIPC.getJSON/postJSON/stream) + native fs/git bridges.
// The renderer is the SAME React app as the web build; only the transport
// implementation differs (IPC here vs fetch/SSE on the web).

const { app, BrowserWindow, ipcMain, dialog } = require("electron");
app.name = "Puppetmaster";
const { spawn } = require("node:child_process");
const http = require("node:http");
const path = require("node:path");
const net = require("node:net");
const fs = require("node:fs");
const os = require("node:os");

const isDev = !!process.env.PMHARNESS_DEV_SERVER;
let backend = null;
let backendPort = 8799;
let win = null;

function freePort() {
  return new Promise((resolve) => {
    const srv = net.createServer();
    srv.listen(0, "127.0.0.1", () => {
      const p = srv.address().port;
      srv.close(() => resolve(p));
    });
  });
}

function waitForBackend(port, timeoutMs = 20000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const probe = () => {
      const req = http.get({ host: "127.0.0.1", port, path: "/api/config", timeout: 2000 }, (res) => {
        res.destroy();
        resolve(true);
      });
      req.on("error", () => {
        if (Date.now() - start > timeoutMs) return reject(new Error("backend did not start"));
        setTimeout(probe, 300);
      });
      req.on("timeout", () => { req.destroy(); });
    };
    probe();
  });
}

// Single-backend-per-machine: a marker file records the live backend port so a
// second window REUSES it instead of spawning another process on the same SQLite
// state (which causes "database is locked"). The marker is validated by a health
// probe before reuse; stale markers are ignored.
function markerPath() {
  const dir = path.join(os.homedir(), ".pmharness");
  try { fs.mkdirSync(dir, { recursive: true }); } catch {}
  return path.join(dir, "backend.json");
}

async function startBackend() {
  // 1. Try to reuse an existing healthy backend.
  try {
    const m = JSON.parse(fs.readFileSync(markerPath(), "utf8"));
    if (m && m.port) {
      await waitForBackend(m.port, 2000);
      backendPort = m.port;
      backend = null; // not ours to kill
      console.log(`[backend] reusing existing backend on ${backendPort}`);
      return;
    }
  } catch {}

  // 2. Spawn a fresh backend on a free port and record the marker.
  backendPort = await freePort();
  // Backend resolution. In dev, __dirname is webapp/electron so ../.. is the repo.
  // When packaged (.asar), that path is invalid -> resolve from env or the known
  // install location. A fully self-contained bundle (PyInstaller) is the next
  // step toward distribution; for a personal build we use the existing venv.
  const { app } = require("electron");
  const repoRoot = process.env.HARNESS_REPO
    || (app.isPackaged ? path.join(os.homedir(), "pm-harness") : path.resolve(__dirname, "..", ".."));

  let binaryPath = null;
  if (app.isPackaged && process.resourcesPath) {
    const p = path.join(process.resourcesPath, "pmharness-backend");
    if (fs.existsSync(p)) {
      binaryPath = p;
    }
  }

  const _dbg = (msg) => { try { fs.appendFileSync(path.join(os.homedir(), ".pmharness", "electron.log"), `${new Date().toISOString()} ${msg}\n`); } catch {} };

  const customEnv = { ...process.env, HARNESS_REPO: process.env.HARNESS_REPO || repoRoot };

  try {
    const shimDir = path.join(app.getPath("userData"), "bin");
    fs.mkdirSync(shimDir, { recursive: true });

    let codegraphJsPath = "";
    if (app.isPackaged) {
      codegraphJsPath = path.join(process.resourcesPath, "codegraph", "dist", "bin", "codegraph.js");
    } else {
      const devVendorPath = path.join(__dirname, "..", "codegraph-vendor", "dist", "bin", "codegraph.js");
      if (fs.existsSync(devVendorPath)) {
        codegraphJsPath = devVendorPath;
      } else {
        const paths = [
          "/opt/homebrew/lib/node_modules/@colbymchenry/codegraph/dist/bin/codegraph.js",
          "/usr/local/lib/node_modules/@colbymchenry/codegraph/dist/bin/codegraph.js",
        ];
        for (const p of paths) {
          if (fs.existsSync(p)) {
            codegraphJsPath = p;
            break;
          }
        }
      }
    }

    if (codegraphJsPath && fs.existsSync(codegraphJsPath)) {
      const codegraphShimPath = path.join(shimDir, "codegraph");
      const codegraphShimContent = `#!/bin/sh
export ELECTRON_RUN_AS_NODE=1
exec "${process.execPath}" -e "process.execArgv = []; process.argv.splice(1, 0, '${codegraphJsPath}'); delete process.versions.electron; require('${codegraphJsPath}')" -- "$@"
`;
      fs.writeFileSync(codegraphShimPath, codegraphShimContent, "utf8");
      fs.chmodSync(codegraphShimPath, 0o755);

      const nodeShimPath = path.join(shimDir, "node");
      const nodeShimContent = `#!/bin/sh
export ELECTRON_RUN_AS_NODE=1
exec "${process.execPath}" "$@"
`;
      fs.writeFileSync(nodeShimPath, nodeShimContent, "utf8");
      fs.chmodSync(nodeShimPath, 0o755);

      _dbg(`Set up codegraph shim in ${shimDir} pointing to ${codegraphJsPath}`);

      customEnv.PATH = shimDir + path.delimiter + (process.env.PATH || "");
      customEnv.PUPPETMASTER_CODEGRAPH_NO_NPX = "1";
    } else {
      _dbg(`Could not locate codegraph.js (isPackaged=${app.isPackaged}). Skipping shim setup.`);
    }
  } catch (e) {
    _dbg(`Failed to setup codegraph shim: ${e.message}`);
  }

  if (binaryPath) {
    _dbg(`spawning bundled binary: ${binaryPath} cwd=${repoRoot} port=${backendPort} packaged=${app.isPackaged}`);
    backend = spawn(binaryPath, ["gui", "--port", String(backendPort)], {
      cwd: repoRoot,
      env: customEnv,
      stdio: ["ignore", "pipe", "pipe"],
    });
  } else {
    const py = process.env.PMHARNESS_PYTHON || path.join(repoRoot, ".venv", "bin", "python");
    _dbg(`spawning python backend: ${py} cwd=${repoRoot} port=${backendPort} packaged=${app.isPackaged}`);
    backend = spawn(py, ["-m", "harness.cli", "gui", "--port", String(backendPort)], {
      cwd: repoRoot,
      env: customEnv,
      stdio: ["ignore", "pipe", "pipe"],
    });
  }

  backend.on("error", (e) => _dbg(`spawn error: ${e.message}`));
  backend.stdout.on("data", (d) => { _dbg(`[out] ${d}`); process.stdout.write(`[backend] ${d}`); });
  backend.stderr.on("data", (d) => { _dbg(`[err] ${d}`); process.stderr.write(`[backend] ${d}`); });
  await waitForBackend(backendPort);
  try { fs.writeFileSync(markerPath(), JSON.stringify({ port: backendPort, pid: backend.pid, at: Date.now() })); } catch {}
}

// ---- transport seam over IPC: proxy to the local backend ----
function authToken() {
  try { return fs.readFileSync(path.join(os.homedir(), ".pmharness", "token"), "utf8").trim(); }
  catch { return ""; }
}

function backendRequest(method, apiPath, body) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;
    const req = http.request({
      host: "127.0.0.1", port: backendPort, path: apiPath, method,
      headers: { "Content-Type": "application/json", "X-Harness-Token": authToken(), ...(data ? { "Content-Length": Buffer.byteLength(data) } : {}) },
    }, (res) => {
      let buf = "";
      res.on("data", (c) => (buf += c));
      res.on("end", () => { try { resolve(JSON.parse(buf || "null")); } catch { resolve(null); } });
    });
    req.on("error", reject);
    if (data) req.write(data);
    req.end();
  });
}

ipcMain.handle("harness:getJSON", (_e, p) => backendRequest("GET", p));
ipcMain.handle("harness:postJSON", (_e, p, body) => backendRequest("POST", p, body));

// Native folder picker (Cursor-style "Open Folder"). Returns absolute path or null.
ipcMain.handle("harness:pickFolder", async () => {
  const res = await dialog.showOpenDialog({ properties: ["openDirectory", "createDirectory"] });
  if (res.canceled || !res.filePaths || !res.filePaths.length) return null;
  return res.filePaths[0];
});

// SSE stream: bridge backend EventSource-style stream to renderer via events.
ipcMain.on("harness:stream", (event, channelId, apiPath) => {
  const tok = authToken();
  const streamPath = tok ? apiPath + (apiPath.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(tok) : apiPath;
  const req = http.get({ host: "127.0.0.1", port: backendPort, path: streamPath }, (res) => {
    res.setEncoding("utf8");
    let buf = "";
    res.on("data", (chunk) => {
      buf += chunk;
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const frame = buf.slice(0, idx); buf = buf.slice(idx + 2);
        const line = frame.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        const payload = line.slice(6);
        try {
          const ev = JSON.parse(payload);
          if (ev.kind === "done") { event.sender.send(`${channelId}:done`); res.destroy(); return; }
          event.sender.send(`${channelId}:event`, ev);
        } catch {}
      }
    });
    res.on("end", () => event.sender.send(`${channelId}:done`));
    res.on("error", (e) => event.sender.send(`${channelId}:error`, String(e)));
  });
  req.on("error", (e) => event.sender.send(`${channelId}:error`, String(e)));
  ipcMain.once(`${channelId}:cancel`, () => req.destroy());
});

// ---- native bridges (file tree + git) ----
const { registerFsBridge } = require("./fs-bridge.cjs");
const { registerGitBridge } = require("./git-bridge.cjs");
registerFsBridge(ipcMain);
registerGitBridge(ipcMain);

function createWindow() {
  win = new BrowserWindow({
    width: 1440, height: 900, backgroundColor: "#0d0d0f",
    titleBarStyle: "hiddenInset",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      webviewTag: true,   // enables the real in-app browser
    },
  });
  // expose the backend port to the renderer for any direct needs
  win.webContents.on("did-finish-load", () => {
    let tok = "";
    try { tok = fs.readFileSync(path.join(os.homedir(), ".pmharness", "token"), "utf8").trim(); } catch {}
    win.webContents.executeJavaScript(
      `window.__HARNESS_PORT__=${backendPort};window.__HARNESS_TOKEN__=${JSON.stringify(tok)};`
    ).catch(() => {});
  });
  if (isDev) win.loadURL(process.env.PMHARNESS_DEV_SERVER);
  else win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
}

app.whenReady().then(async () => {
  try { await startBackend(); } catch (e) { console.error("backend start failed:", e); }
  createWindow();
  app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

function cleanupBackend() {
  if (backend) {
    try { fs.unlinkSync(markerPath()); } catch {}
    backend.kill();
    backend = null;
  }
}
app.on("window-all-closed", () => {
  cleanupBackend();
  if (process.platform !== "darwin") app.quit();
});
app.on("before-quit", cleanupBackend);
