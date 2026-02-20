#!/bin/zsh
set -euo pipefail

DEST_DIR="$HOME/Library/LaunchAgents"

remove_agent() {
  local name="$1"
  local dest="$DEST_DIR/$name.plist"

  launchctl bootout "gui/$UID" "$dest" >/dev/null 2>&1 || true
  rm -f "$dest"
  echo "Removed $name"
}

remove_agent "com.therapyops.acorn-preflight"
remove_agent "com.therapyops.acorn-send"
