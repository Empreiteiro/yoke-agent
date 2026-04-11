#!/usr/bin/env sh
# Yoke Agent CLI installer.
#
#   curl -fsSL https://raw.githubusercontent.com/Empreiteiro/yoke-agent/main/install.sh | sh
#
# What this does:
#   1. Ensures Python 3.10+ and pipx are available (auto-installs pipx
#      via brew/apt/pip when possible).
#   2. Clones (or updates) the Yoke repo to ~/.yoke/repo.
#   3. Installs the `yoke-cli` package from cli/ via pipx.
#   4. Records the local checkout path so `yoke serve` can later spin
#      up the docker stack.
#
# Environment overrides:
#   YOKE_HOME    — install root (default: ~/.yoke)
#   YOKE_BRANCH  — git branch to clone (default: main)
#   YOKE_REPO    — git URL (default: https://github.com/Empreiteiro/yoke-agent.git)

set -eu

YOKE_HOME="${YOKE_HOME:-$HOME/.yoke}"
YOKE_BRANCH="${YOKE_BRANCH:-main}"
YOKE_REPO="${YOKE_REPO:-https://github.com/Empreiteiro/yoke-agent.git}"
REPO_DIR="$YOKE_HOME/repo"

# ── tiny helpers ────────────────────────────────────────────────────
say()  { printf '\033[36m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m  ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[33m  !\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m  ✗\033[0m %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

# ── 1. python ───────────────────────────────────────────────────────
say "Checking prerequisites"
if ! have python3; then
  die "python3 not found. Install Python 3.10+ and re-run."
fi
PY_VERSION=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
PY_OK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3,10) else 0)')
if [ "$PY_OK" != "1" ]; then
  die "python3 $PY_VERSION found, but Yoke needs >= 3.10."
fi
ok "python3 $PY_VERSION"

# ── 2. git ──────────────────────────────────────────────────────────
if ! have git; then
  die "git not found. Install git and re-run."
fi
ok "git $(git --version | awk '{print $3}')"

# ── 3. pipx ─────────────────────────────────────────────────────────
if ! have pipx; then
  say "Installing pipx"
  if have brew; then
    brew install pipx
  elif have apt-get; then
    sudo apt-get update -qq && sudo apt-get install -y --no-install-recommends pipx
  elif have dnf; then
    sudo dnf install -y pipx
  elif have pacman; then
    sudo pacman -S --noconfirm python-pipx
  else
    python3 -m pip install --user --quiet pipx || die "Failed to install pipx via pip."
  fi
  python3 -m pipx ensurepath >/dev/null 2>&1 || true
  if ! have pipx; then
    # pipx may have been installed but isn't on PATH yet.
    PIPX_BIN="$HOME/.local/bin/pipx"
    [ -x "$PIPX_BIN" ] && PATH="$HOME/.local/bin:$PATH" && export PATH
  fi
  have pipx || die "pipx still not available after install. Open a new shell and re-run."
fi
ok "pipx $(pipx --version 2>/dev/null || echo unknown)"

# ── 4. clone / update the repo ──────────────────────────────────────
mkdir -p "$YOKE_HOME"
if [ -d "$REPO_DIR/.git" ]; then
  say "Updating Yoke repo at $REPO_DIR"
  git -C "$REPO_DIR" fetch --quiet origin "$YOKE_BRANCH"
  git -C "$REPO_DIR" reset --quiet --hard "origin/$YOKE_BRANCH"
else
  say "Cloning $YOKE_REPO → $REPO_DIR"
  git clone --quiet --branch "$YOKE_BRANCH" --depth 1 "$YOKE_REPO" "$REPO_DIR"
fi
ok "repo ready"

# ── 5. install yoke-cli via pipx ────────────────────────────────────
say "Installing yoke-cli via pipx"
pipx install --force "$REPO_DIR/cli" >/dev/null
ok "yoke-cli installed"

# ── 6. record the repo path so `yoke serve` can find it ─────────────
mkdir -p "$YOKE_HOME"
CONFIG_FILE="$YOKE_HOME/config.json"
python3 - "$CONFIG_FILE" "$REPO_DIR" <<'PYEOF'
import json, os, sys
path, repo = sys.argv[1], sys.argv[2]
data = {}
if os.path.exists(path):
    try:
        data = json.loads(open(path).read())
    except Exception:
        data = {}
data["repo_path"] = repo
with open(path, "w") as f:
    json.dump(data, f, indent=2, sort_keys=True)
    f.write("\n")
os.chmod(path, 0o600)
PYEOF
ok "recorded repo_path → $CONFIG_FILE"

# ── 7. final hint ───────────────────────────────────────────────────
echo
if have yoke; then
  ok "Yoke CLI installed: $(yoke --version 2>/dev/null || echo yoke)"
else
  warn "'yoke' not on PATH yet. Run 'pipx ensurepath' and reopen your shell."
fi
echo
echo "Next steps:"
echo "  1. Edit $REPO_DIR/backend/.env to add provider API keys"
echo "  2. Run 'yoke serve' to start the local stack via docker compose"
echo "  3. Run 'yoke doctor' to verify connectivity"
echo "  4. Run 'yoke --help' to see all commands"
echo
