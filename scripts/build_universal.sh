#!/bin/bash
set -euo pipefail

# Resolve script directory and repository root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$REPO_ROOT"

# 1. Detection of universal2 Python
UNIVERSAL_PYTHON_PATH=""

if [ -n "${UNIVERSAL_PYTHON:-}" ]; then
    if [ ! -f "$UNIVERSAL_PYTHON" ]; then
        echo "Error: UNIVERSAL_PYTHON is set to '$UNIVERSAL_PYTHON' but file does not exist."
        exit 1
    fi
    ARCHS=$(lipo -archs "$UNIVERSAL_PYTHON" 2>/dev/null || true)
    if [[ "$ARCHS" == *"arm64"* && "$ARCHS" == *"x86_64"* ]]; then
        UNIVERSAL_PYTHON_PATH="$UNIVERSAL_PYTHON"
    else
        echo "Error: Provided Python at '$UNIVERSAL_PYTHON' is not a universal2 binary."
        echo "Architectures found: $ARCHS"
        exit 1
    fi
else
    echo "UNIVERSAL_PYTHON is not set, attempting to auto-detect a likely universal2 python..."
    # Gather candidates
    CANDIDATES=()
    # Check framework paths (need a loop to avoid literal *)
    for f in /Library/Frameworks/Python.framework/Versions/*/bin/python3; do
        if [ -f "$f" ]; then
            CANDIDATES+=("$f")
        fi
    done
    if [ -f "/usr/local/bin/python3" ]; then
        CANDIDATES+=("/usr/local/bin/python3")
    fi

    # Evaluate candidates
    for cand in "${CANDIDATES[@]}"; do
        ARCHS=$(lipo -archs "$cand" 2>/dev/null || true)
        if [[ "$ARCHS" == *"arm64"* && "$ARCHS" == *"x86_64"* ]]; then
            UNIVERSAL_PYTHON_PATH="$cand"
            echo "Auto-detected universal2 python at: $UNIVERSAL_PYTHON_PATH (architectures: $ARCHS)"
            break
        fi
    done
fi

# 2. Check if a universal2 Python was successfully identified
if [ -z "$UNIVERSAL_PYTHON_PATH" ]; then
    echo "--------------------------------------------------------"
    echo "No universal2 Python was found on this system."
    echo "A universal2 Python is required to build a universal2 macOS app."
    echo "To install one, please download and run the official macOS installer from:"
    echo "  https://www.python.org/downloads/macos/"
    echo "  (The official macOS installer packages from python.org ship universal2 binaries)"
    echo "Alternatively, export UNIVERSAL_PYTHON pointing to a universal2 python3 binary."
    echo "--------------------------------------------------------"
    exit 1
fi

echo "Using universal2 Python: $UNIVERSAL_PYTHON_PATH"

# 3a. Create separate universal2 venv (.venv-universal)
if [ ! -d ".venv-universal" ]; then
    echo "Creating separate virtual environment .venv-universal..."
    "$UNIVERSAL_PYTHON_PATH" -m venv .venv-universal
fi

echo "Upgrading pip and installing dependencies into .venv-universal..."
.venv-universal/bin/pip install --upgrade pip

echo "Installing pm-harness in editable mode with dev dependencies..."
.venv-universal/bin/pip install -e ".[dev]"

# Detect and preserve puppetmaster-ai editable install if it exists in the standard .venv
PUPPETMASTER_DIR=""
if [ -f ".venv/bin/python" ]; then
    PUPPETMASTER_DIR=$(.venv/bin/python -c "import os, puppetmaster; print(os.path.abspath(os.path.join(os.path.dirname(puppetmaster.__file__), '..')))" 2>/dev/null || echo "")
fi

if [ -n "$PUPPETMASTER_DIR" ] && [ -d "$PUPPETMASTER_DIR" ]; then
    echo "Installing puppetmaster-ai in editable mode into .venv-universal..."
    .venv-universal/bin/pip install -e "$PUPPETMASTER_DIR"
fi

# 3b. Run PyInstaller with PMHARNESS_TARGET_ARCH=universal2
echo "Building universal2 PyInstaller backend..."
export PMHARNESS_TARGET_ARCH="universal2"
.venv-universal/bin/pyinstaller --clean --distpath webapp/backend-dist --workpath build/pyinstaller-work build/pmharness-backend.spec

# 3c. Verify produced binary with lipo
echo "Verifying the produced backend binary architecture..."
BACKEND_BIN="webapp/backend-dist/pmharness-backend"
if [ ! -f "$BACKEND_BIN" ]; then
    echo "Error: Backend binary was not produced at $BACKEND_BIN"
    exit 1
fi

BIN_ARCHS=$(lipo -archs "$BACKEND_BIN" 2>/dev/null || true)
echo "Produced backend architectures: $BIN_ARCHS"

if [[ ! "$BIN_ARCHS" == *"arm64"* || ! "$BIN_ARCHS" == *"x86_64"* ]]; then
    echo "CRITICAL ERROR: Produced backend binary at $BACKEND_BIN is not universal2!"
    echo "Architectures found: $BIN_ARCHS"
    exit 1
fi

echo "Verification success: backend binary is universal2!"

# 3d. Build the universal app using electron-builder
echo "Building the universal Electron desktop application DMG..."
cd webapp
npm run build
npx electron-builder --mac dmg --universal

# Confirm dmg is produced
echo "Confirming DMG is produced under webapp/release/..."
DMG_COUNT=$(find release -maxdepth 1 -name "*.dmg" | wc -l | tr -d ' ')
if [ "$DMG_COUNT" -eq 0 ]; then
    echo "Error: No DMG was found in webapp/release/"
    exit 1
fi

echo "Universal2 app build complete! DMG files generated:"
find release -maxdepth 1 -name "*.dmg"
