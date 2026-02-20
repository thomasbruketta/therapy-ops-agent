#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
TEMPLATE_DIR="$REPO_ROOT/ops/launchd"
DEST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="${ACORN_AUTOMATION_LOG_DIR:-$HOME/Library/Logs/therapy-ops-agent}"

mkdir -p "$DEST_DIR" "$LOG_DIR"

report_to="${ACORN_AUTOMATION_REPORT_TO:-}"
docker_timeout="${ACORN_DOCKER_READY_TIMEOUT_SEC:-120}"

if [[ -z "$report_to" && -f "$REPO_ROOT/.env.local" ]]; then
  report_to="$(grep -E '^ACORN_AUTOMATION_REPORT_TO=' "$REPO_ROOT/.env.local" | tail -n 1 | cut -d '=' -f2- | tr -d '"' | tr -d "'" || true)"
fi

if [[ -z "${ACORN_DOCKER_READY_TIMEOUT_SEC:-}" && -f "$REPO_ROOT/.env.local" ]]; then
  parsed_timeout="$(grep -E '^ACORN_DOCKER_READY_TIMEOUT_SEC=' "$REPO_ROOT/.env.local" | tail -n 1 | cut -d '=' -f2- | tr -d '"' | tr -d "'" || true)"
  if [[ -n "$parsed_timeout" ]]; then
    docker_timeout="$parsed_timeout"
  fi
fi

escape_sed() {
  printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'
}

render_template() {
  local template_path="$1"
  local output_path="$2"
  sed \
    -e "s|__REPO_ROOT__|$(escape_sed "$REPO_ROOT")|g" \
    -e "s|__HOME__|$(escape_sed "$HOME")|g" \
    -e "s|__REPORT_TO__|$(escape_sed "$report_to")|g" \
    -e "s|__DOCKER_TIMEOUT__|$(escape_sed "$docker_timeout")|g" \
    "$template_path" > "$output_path"
}

install_agent() {
  local name="$1"
  local template="$TEMPLATE_DIR/$name.plist"
  local dest="$DEST_DIR/$name.plist"
  local label="$name"

  if [[ ! -f "$template" ]]; then
    echo "Template not found: $template" >&2
    exit 1
  fi

  local rendered
  rendered="$(mktemp)"
  render_template "$template" "$rendered"

  launchctl bootout "gui/$UID" "$dest" >/dev/null 2>&1 || true
  cp "$rendered" "$dest"
  rm -f "$rendered"

  launchctl bootstrap "gui/$UID" "$dest"
  launchctl enable "gui/$UID/$label" >/dev/null 2>&1 || true

  echo "Installed $label -> $dest"
}

install_agent "com.therapyops.acorn-preflight"
install_agent "com.therapyops.acorn-send"

echo "LaunchAgents installed. Logs: $LOG_DIR"
if [[ -z "$report_to" ]]; then
  echo "Warning: ACORN_AUTOMATION_REPORT_TO is empty; report emails will be skipped." >&2
fi
