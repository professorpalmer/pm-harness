# Packaging PM Harness (macOS)

The desktop app is an Electron shell (`webapp/`) that spawns the Python backend
(`harness.cli gui`) and talks to it over a localhost loopback + auth token.

## Build an installable app (personal / unsigned)

```
cd webapp
npm install            # once
npm run dist:mac       # -> webapp/release/mac-arm64/PM Harness.app
```

Double-click `PM Harness.app` (or drag to /Applications). On first launch macOS
Gatekeeper will warn it is unsigned: right-click -> Open, or
`xattr -dr com.apple.quarantine "PM Harness.app"`.

## Backend dependency (current limitation, stated honestly)

The packaged app does NOT yet bundle Python. It resolves the backend at runtime:

1. `PMHARNESS_PYTHON` env var (explicit python), else
2. `HARNESS_REPO/.venv/bin/python`, where `HARNESS_REPO` defaults to
   `~/pm-harness` when packaged.

So the app currently requires the repo + its `.venv` present at `~/pm-harness`.
This is fine for personal use; it is NOT a self-contained distributable yet.

### Path to a self-contained bundle (next step, not done)

Bundle the backend with PyInstaller and ship the binary inside the app's
`Resources/`, then point the spawn at `process.resourcesPath`. That removes the
venv dependency and makes the app portable to machines without the repo. Tracked
as a TODO; deliberately not done yet (internal-first; the venv path works for the
author's own daily-driver use).

## Code signing + notarization (required only for distribution)

An unsigned build runs locally. To distribute to other machines without Gatekeeper
friction you need an Apple Developer account ($99/yr):

```
# in package.json build.mac: set identity to your "Developer ID Application" cert
# then notarize with @electron/notarize (APPLE_ID, APPLE_APP_SPECIFIC_PASSWORD,
# APPLE_TEAM_ID) and staple.
```

Not configured here — the current target is `dir`/unsigned for personal use.

## What the build produces

- `release/mac-arm64/PM Harness.app` (~260 MB; Electron runtime + dist + electron/)
- Verified: launches, spawns the backend, serves /api/config|skills|mcp (200),
  single shared backend per machine (marker reuse), auth token enforced.
