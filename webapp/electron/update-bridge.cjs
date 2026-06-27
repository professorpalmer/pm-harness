// Tier-1 update check (manual-install, Cursor/Hermes-style "update available" nudge).
//
// This does NOT auto-download or self-install. It queries the GitHub Releases
// API for the latest published release, compares its tag to the running app
// version, and if a newer version exists returns metadata the renderer surfaces
// as a quiet footnote with a "download" link. The user installs the DMG by hand.
//
// Why this tier: the repo is private and we deliberately do not ship a GitHub
// token inside the app, so full electron-updater auto-install is out of scope.
// If the API call fails for any reason we fail SILENT (no nag, no error popup)
// -- an update check must never get in the user's way.

const https = require("node:https");

// The repo whose Releases feed we check. Override with PMHARNESS_UPDATE_REPO
// (form "owner/name") for testing against a fork.
const UPDATE_REPO = process.env.PMHARNESS_UPDATE_REPO || "professorpalmer/pm-harness";

// Parse a semver-ish string ("v0.4.1", "0.4.1", "0.4.1-beta") into comparable
// numeric parts. Returns [major, minor, patch] or null if unparseable.
function parseVersion(v) {
  if (!v || typeof v !== "string") return null;
  const cleaned = v.trim().replace(/^v/i, "").split("-")[0].split("+")[0];
  const parts = cleaned.split(".").map((p) => parseInt(p, 10));
  if (parts.length < 1 || parts.some((n) => Number.isNaN(n))) return null;
  return [parts[0] || 0, parts[1] || 0, parts[2] || 0];
}

// Returns 1 if a > b, -1 if a < b, 0 if equal. Unparseable -> 0 (no update offered).
function compareVersions(a, b) {
  const pa = parseVersion(a);
  const pb = parseVersion(b);
  if (!pa || !pb) return 0;
  for (let i = 0; i < 3; i++) {
    if (pa[i] > pb[i]) return 1;
    if (pa[i] < pb[i]) return -1;
  }
  return 0;
}

function fetchLatestRelease() {
  return new Promise((resolve, reject) => {
    const options = {
      host: "api.github.com",
      path: `/repos/${UPDATE_REPO}/releases/latest`,
      method: "GET",
      headers: {
        "User-Agent": "Marionette-Updater",
        Accept: "application/vnd.github+json",
      },
      timeout: 8000,
    };
    const req = https.request(options, (res) => {
      let buf = "";
      res.on("data", (c) => (buf += c));
      res.on("end", () => {
        if (res.statusCode !== 200) {
          return reject(new Error(`GitHub releases API status ${res.statusCode}`));
        }
        try {
          resolve(JSON.parse(buf));
        } catch (e) {
          reject(e);
        }
      });
    });
    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy();
      reject(new Error("update check timed out"));
    });
    req.end();
  });
}

// Pick the best downloadable asset URL from a release: prefer a .dmg, else the
// release's html_url so the user always has somewhere to go.
function pickDownloadUrl(release) {
  const assets = release.assets || [];
  const dmg = assets.find((a) => (a.name || "").toLowerCase().endsWith(".dmg"));
  if (dmg && dmg.browser_download_url) return dmg.browser_download_url;
  return release.html_url || `https://github.com/${UPDATE_REPO}/releases`;
}

// Compare currentVersion against the latest release.
async function checkForUpdate(currentVersion) {
  try {
    const release = await fetchLatestRelease();
    if (release.draft || release.prerelease) {
      return { available: false };
    }
    const latestTag = release.tag_name || release.name || "";
    if (compareVersions(latestTag, currentVersion) === 1) {
      return {
        available: true,
        version: latestTag.replace(/^v/i, ""),
        name: release.name || latestTag,
        url: pickDownloadUrl(release),
        notes: (release.body || "").slice(0, 2000),
      };
    }
    return { available: false };
  } catch (e) {
    return { available: false, error: String(e && e.message ? e.message : e) };
  }
}

function registerUpdateBridge(ipcMain, app, shell) {
  ipcMain.handle("updates:check", async () => {
    const current = app.getVersion();
    const result = await checkForUpdate(current);
    return { current, ...result };
  });

  // Open the download URL (DMG or Releases page) in the default browser.
  ipcMain.handle("updates:openDownload", async (_e, url) => {
    const safe = typeof url === "string" && /^https:\/\//i.test(url) ? url : null;
    if (!safe) return false;
    try {
      await shell.openExternal(safe);
      return true;
    } catch {
      return false;
    }
  });
}

module.exports = { registerUpdateBridge, checkForUpdate, compareVersions, parseVersion };
