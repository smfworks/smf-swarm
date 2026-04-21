#!/usr/bin/env bash
# SMF Swarm — One-line installer for macOS / Linux
# Usage: curl -fsSL https://raw.githubusercontent.com/smfworks/smf-swarm/main/install.sh | bash

set -euo pipefail

REPO="https://github.com/smfworks/smf-swarm"
BRANCH="main"
PYTHON_MIN="3.10"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║         SMF Swarm — One-Line Installer                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# ── 1. Check Python ───────────────────────────────
PYTHON_CMD=""
for cmd in python3 python3.12 python3.11 python3.10; do
    if command -v "$cmd" > /dev/null 2>&1; then
        VER=$($cmd --version 2>&1 | awk '{print $2}')
        # Check if version >= 3.10
        if [ "$(printf '%s\n' "$PYTHON_MIN" "$VER" | sort -V | head -n1)" = "$PYTHON_MIN" ]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Python $PYTHON_MIN or higher is required."
    echo "   Install Python: https://python.org/downloads/"
    exit 1
fi

echo "✅ Python found: $PYTHON_CMD ($( $PYTHON_CMD --version ))"

# ── 2. Check pip ──────────────────────────────────
if ! command -v pip3 > /dev/null 2>&1 && ! command -v pip > /dev/null 2>&1; then
    echo "❌ pip not found. Please install pip:"
    echo "   curl https://bootstrap.pypa.io/get-pip.py | $PYTHON_CMD"
    exit 1
fi
PIPCMD="pip3"
command -v pip3 > /dev/null 2>&1 || PIPCMD="pip"
echo "✅ pip found: $PIPCMD"

# ── 3. Install package ──────────────────────────
echo ""
echo "📦 Installing smf-swarm from PyPI..."
echo ""
$PIPCMD install --upgrade smf-swarm

# ── 4. Verify ───────────────────────────────────
echo ""
echo "🔍 Verifying installation..."
if command -v smf-swarm > /dev/null 2>&1; then
    smf-swarm version
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║     ✅ SMF Swarm installed successfully!                   ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Next steps:"
    echo "  1. smf-swarm configure       # Run the setup wizard"
    echo "  2. smf-swarm test            # Verify your LLM connection"
    echo "  3. smf-swarm predict \"Will X happen?\" --mode full"
    echo ""
    echo "Documentation: https://github.com/smfworks/smf-swarm"
    echo "Support:       michael@smfworks.com | @michaelgannotti"
    exit 0
else
    echo ""
    echo "⚠️  Installation completed but 'smf-swarm' command not found in PATH."
    echo "   Try:  $PIPCMD install --user smf-swarm"
    echo "   Then: export PATH=\"\$HOME/.local/bin:\$PATH\""
    exit 1
fi
