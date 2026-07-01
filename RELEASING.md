# Releasing Marionette

Marionette delivers updates two ways behind one status-bar pill. Which one runs
is decided automatically by whether the app is an installed `.app` or a git
checkout.

## 1. Installed app -- background auto-update (primary)

The shipped `.app` is the "real app": install it once from the DMG, and from
then on it updates itself. New releases published to GitHub Releases are
downloaded in the background and applied on the next relaunch -- no script, no
re-downloading a DMG per change. This is the Hermes Desktop model, implemented
with `electron-updater` (`webapp/electron/auto-updater.cjs`).

How it reaches everyone:

1. You cut a signed release (below). electron-builder publishes the `.dmg`, the
   `.zip`, and `latest-mac.yml` to the GitHub Release.
2. Every installed app checks the release feed on launch (and every 6h), sees a
   newer version, and downloads the `.zip` in the background.
3. The status-bar `update` pill lights up; clicking it (or just quitting and
   reopening) swaps the whole signed bundle and relaunches on the new version.

### Cutting a signed release

```bash
bash scripts/release.sh X.Y.Z "release notes"
```

This bumps `webapp/package.json`, builds the notarized DMG **and** the
auto-update `.zip` + `latest-mac.yml`, tags `vX.Y.Z`, and uploads every
auto-update artifact (dmg, zip, latest-mac.yml, blockmaps) to the GitHub
Release.

**macOS requires the release to be Developer ID signed + notarized** -- an
unsigned build will download but macOS will refuse to apply it. So the
notarization creds must be in the environment (`APPLE_ID`, `APPLE_TEAM_ID`,
`APPLE_APP_SPECIFIC_PASSWORD`) alongside the signing cert (Developer ID
Application: Cary Palmer, ZDSDN9VC8M). See `webapp/PACKAGING.md`. If those are
absent the build is unsigned and auto-update will not apply.

## 2. Git checkout -- self-update from source (contributors)

Running from a source checkout (contributors hacking on Marionette) has no
signed bundle to swap, so the same pill instead pulls + rebuilds in place:

- `git fetch` + `git merge --ff-only` the tracked branch tip,
- `pip install -e .` **only if** a Python dep file changed,
- `npm ci` **only if** `webapp/package-lock.json` changed,
- `npm run build` (retry once) to rebuild the renderer,
- relaunch (backend torn down first so it comes back on the new code).

Fast-forward only: local commits or uncommitted changes stop the update with a
clear message instead of rewriting the tree. Implementation lives in
`webapp/electron/update-*.cjs` (pure helpers, unit tested via
`npm run test:electron`) and `update-bridge.cjs`. Adapted with attribution from
the Hermes Agent desktop updater (MIT, Nous Research).
