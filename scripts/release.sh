#!/bin/bash
# One-command Tier-1 release: build the notarized DMG and publish a GitHub Release
# so testers' apps see the "update available" nudge.
#
# Usage:  scripts/release.sh 0.4.1   ["release notes line"]
#
# What it does, in order:
#   1. Sanity: clean tree, on main, gh authed as professorpalmer.
#   2. Sets webapp/package.json version to the given version.
#   3. Builds the fully self-contained notarized DMG (dist:full).
#   4. Commits the version bump, tags vX.Y.Z, pushes both.
#   5. Creates a GitHub Release on professorpalmer/pm-harness with the DMG attached.
#
# REQUIRES (env, single-use, not persisted): Apple notarization creds already in
# the environment the same way dist:full expects them (APPLE_ID / APPLE_TEAM_ID /
# APPLE_APP_SPECIFIC_PASSWORD). gh must be authed; we force the professorpalmer
# account. The PUBLIC release makes the DMG downloadable; source stays private.
set -euo pipefail

VERSION="${1:-}"
NOTES="${2:-}"
if [ -z "$VERSION" ]; then
  echo "usage: scripts/release.sh X.Y.Z [\"notes\"]" >&2
  exit 1
fi
# strip any leading v the user typed
VERSION="${VERSION#v}"
TAG="v${VERSION}"

REPO_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$REPO_ROOT"

echo "== preflight =="
if [ -n "$(git status --porcelain | grep -v 'results/')" ]; then
  echo "ERROR: working tree is dirty. Commit or stash first." >&2
  git status --short | grep -v 'results/' >&2
  exit 1
fi
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" != "main" ]; then
  echo "ERROR: not on main (on $BRANCH)." >&2
  exit 1
fi
# releases push as professorpalmer (gh drifts to cary_jepp)
gh auth switch --user professorpalmer >/dev/null 2>&1 || true

echo "== set version $VERSION =="
python3 - "$VERSION" <<'PY'
import json, sys, re
v = sys.argv[1]
p = "webapp/package.json"
s = open(p).read()
s = re.sub(r'"version":\s*"[^"]*"', f'"version": "{v}"', s, count=1)
open(p, "w").write(s)
print("package.json ->", v)
PY

echo "== build notarized DMG + auto-update zip (dist:full) -- this is the slow part =="
( cd webapp && npm run dist:full )

DMG="$(ls -t webapp/release/*.dmg 2>/dev/null | head -1 || true)"
if [ -z "$DMG" ] || [ ! -f "$DMG" ]; then
  echo "ERROR: no DMG produced under webapp/release/." >&2
  exit 1
fi
echo "built: $DMG"

# electron-updater (installed .app auto-update) needs the zip + latest-mac.yml
# (and their blockmaps for delta downloads) on the release, not just the DMG.
ZIP="$(ls -t webapp/release/*.zip 2>/dev/null | head -1 || true)"
LATEST_YML="webapp/release/latest-mac.yml"
if [ -z "$ZIP" ] || [ ! -f "$ZIP" ] || [ ! -f "$LATEST_YML" ]; then
  echo "ERROR: missing auto-update artifacts (zip / latest-mac.yml) under webapp/release/." >&2
  echo "       Installed apps would NOT auto-update. Check the mac targets + publish config." >&2
  exit 1
fi
echo "built: $ZIP"

# Every artifact electron-updater consults, in one array (blockmaps are optional
# but enable delta downloads, so upload them when present).
UPDATE_ASSETS=( "$DMG" "$ZIP" "$LATEST_YML" )
[ -f "${DMG}.blockmap" ] && UPDATE_ASSETS+=( "${DMG}.blockmap" )
[ -f "${ZIP}.blockmap" ] && UPDATE_ASSETS+=( "${ZIP}.blockmap" )

echo "== commit + tag + push =="
git -c user.name=professorpalmer -c user.email=professorpalmer@users.noreply.github.com \
  add webapp/package.json
git -c user.name=professorpalmer -c user.email=professorpalmer@users.noreply.github.com \
  commit -q -m "release: ${TAG}" || echo "(nothing to commit)"
git tag -f "$TAG"
git push origin main
git push -f origin "$TAG"

echo "== github release =="
REL_NOTES="${NOTES:-Marionette ${VERSION}}"
if gh release view "$TAG" --repo professorpalmer/pm-harness >/dev/null 2>&1; then
  gh release upload "$TAG" "${UPDATE_ASSETS[@]}" --repo professorpalmer/pm-harness --clobber
else
  gh release create "$TAG" "${UPDATE_ASSETS[@]}" \
    --repo professorpalmer/pm-harness \
    --title "Marionette ${VERSION}" \
    --notes "$REL_NOTES" \
    --latest
fi

# --- keep the release folder tidy ---------------------------------------------
# electron-builder leaves stale blockmaps, orphan .zip/.dmg from prior builds,
# and a .DS_Store behind every run. Prune everything that is not THIS release's
# DMG (+ its blockmap), the active mac-arm64 staging dir, or builder metadata, so
# webapp/release/ does not pile up to gigabytes over many releases.
REL_DIR="webapp/release"
KEEP_DMG="$(basename "$DMG")"
KEEP_ZIP="$(basename "$ZIP")"
echo
echo "Pruning stale artifacts from ${REL_DIR}/ (keeping ${KEEP_DMG} + ${KEEP_ZIP}) ..."
if [ -d "$REL_DIR" ]; then
  for f in "$REL_DIR"/*; do
    [ -e "$f" ] || continue
    base="$(basename "$f")"
    case "$base" in
      "$KEEP_DMG"|"${KEEP_DMG}.blockmap"|"$KEEP_ZIP"|"${KEEP_ZIP}.blockmap"|"mac-arm64"|"builder-debug.yml"|"latest-mac.yml"|"latest.yml")
        : ;;  # keep
      *)
        rm -rf "$f" && echo "  pruned ${base}" ;;
    esac
  done
fi

echo
echo "DONE. Release ${TAG} published with $(basename "$DMG") + auto-update assets."
echo "Installed apps on an older build will download ${VERSION} in the background and apply it on the next relaunch."
