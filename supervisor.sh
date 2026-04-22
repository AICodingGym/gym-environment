#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_PATH="$ROOT_DIR/dashboard.html"
NOTEBOOK_PATH="$ROOT_DIR/solution.ipynb"
SNAPSHOT_DIR="$ROOT_DIR/.supervisor_snapshot"
LOCK_FILE="$ROOT_DIR/.supervisor.lock"
HELPER="$ROOT_DIR/tools/notebook_metrics.py"

# Update these for each problem folder as needed.
DEFAULT_CMD="aicodinggym mle log show <competition_or_problem_id>"
SUBMIT_CMD="aicodinggym mle submit <competition_or_problem_id> -F submission.csv"

timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

html_escape() {
  sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

ensure_dashboard() {
  if [[ -f "$DASHBOARD_PATH" ]]; then
    return
  fi
  cat >"$DASHBOARD_PATH" <<'EOF'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta http-equiv="refresh" content="5" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI Coding Gym Supervisor Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; background: #111; color: #eee; }
    .card { border: 1px solid #333; border-radius: 8px; padding: 12px; margin-bottom: 12px; background: #1b1b1b; }
    .time { color: #9aa; font-size: 12px; margin-bottom: 8px; }
    pre { white-space: pre-wrap; margin: 0; font-size: 12px; }
    .plus { color: #6be675; }
    .minus { color: #ff7b72; }
    .meta { color: #9cc7ff; margin: 4px 0 8px; }
  </style>
</head>
<body>
  <h1>AI Coding Gym Supervisor Dashboard</h1>
</body>
</html>
EOF
}

append_card() {
  local title="$1"
  local meta="$2"
  local body_html="$3"
  local temp_file
  temp_file="$(mktemp)"
  awk '
    /<\/body>/ { exit }
    { print }
  ' "$DASHBOARD_PATH" >"$temp_file"
  {
    printf '<div class="card">\n'
    printf '  <div class="time">%s</div>\n' "$(timestamp)"
    printf '  <h3>%s</h3>\n' "$title"
    if [[ -n "$meta" ]]; then
      printf '  <div class="meta">%s</div>\n' "$meta"
    fi
    printf '%s\n' "$body_html"
    printf '</div>\n'
    printf '</body>\n</html>\n'
  } >>"$temp_file"
  mv "$temp_file" "$DASHBOARD_PATH"
}

snapshot_workspace() {
  rm -rf "$SNAPSHOT_DIR"
  mkdir -p "$SNAPSHOT_DIR"
  rsync -a --delete \
    --exclude ".git" \
    --exclude ".supervisor_snapshot" \
    --exclude ".supervisor.lock" \
    "$ROOT_DIR/" "$SNAPSHOT_DIR/"
}

diff_to_html() {
  local diff_output
  diff_output="$(diff -ruN "$SNAPSHOT_DIR" "$ROOT_DIR" || true)"
  diff_output="$(printf "%s\n" "$diff_output" | grep -Ev "^Only in .*/(\.supervisor_snapshot|__pycache__)" || true)"
  diff_output="$(printf "%s\n" "$diff_output" | grep -Ev '/dashboard\.html|/\.supervisor_snapshot|/\.supervisor\.lock' || true)"
  if [[ -z "$diff_output" ]]; then
    printf '<pre>No file changes detected.</pre>'
    return
  fi

  local escaped
  escaped="$(printf "%s\n" "$diff_output" | html_escape)"
  escaped="$(printf "%s\n" "$escaped" | sed -E 's#^(\+.*)$#<span class="plus">\1</span>#')"
  escaped="$(printf "%s\n" "$escaped" | sed -E 's#^(-.*)$#<span class="minus">\1</span>#')"
  printf '<pre>%s</pre>' "$escaped"
}

run_notebook_and_log_metric() {
  if [[ ! -f "$NOTEBOOK_PATH" ]]; then
    append_card "Notebook Automation" "Notebook missing" "<pre>Expected $NOTEBOOK_PATH</pre>"
    return
  fi
  local output
  set +e
  output="$(python "$HELPER" "$NOTEBOOK_PATH" 2>&1)"
  local status=$?
  set -e
  local max_acc
  max_acc="$(printf "%s\n" "$output" | grep -oE 'MAX_VALIDATION_ACCURACY=[^[:space:]]+' | tail -n1 | cut -d= -f2 || true)"
  [[ -z "${max_acc:-}" ]] && max_acc="NA"
  local body
  body="$(printf "%s\n" "$output" | html_escape)"
  append_card "Notebook Automation" "MAX_VALIDATION_ACCURACY=${max_acc} (status=${status})" "<pre>${body}</pre>"
}

run_wrapped_command() {
  local command="$1"
  ensure_dashboard
  snapshot_workspace

  local command_output
  set +e
  command_output="$(bash -lc "$command" 2>&1)"
  local status=$?
  set -e

  sleep 1
  local changes_html
  changes_html="$(diff_to_html)"
  append_card "Execution Interception" "command: $command (exit=${status})" "$changes_html"
  append_card "Command Output" "" "<pre>$(printf "%s\n" "$command_output" | html_escape)</pre>"
  run_notebook_and_log_metric
}

submit_flow() {
  ensure_dashboard
  local output
  set +e
  output="$(bash -lc "$SUBMIT_CMD" 2>&1)"
  local status=$?
  set -e

  local ground_truth
  ground_truth="$(printf "%s\n" "$output" | grep -oEi 'ground[ _-]?truth[^0-9]*[0-9]+(\.[0-9]+)?' | head -n1 || true)"
  [[ -z "${ground_truth:-}" ]] && ground_truth="Ground Truth: not found in output"
  append_card "Final Result" "submit exit=${status}" "<pre>$(printf "%s\n%s\n" "$ground_truth" "$output" | html_escape)</pre>"

  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$DASHBOARD_PATH" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$DASHBOARD_PATH" >/dev/null 2>&1 || true
  elif command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command "Start-Process '$DASHBOARD_PATH'" >/dev/null 2>&1 || true
  fi
}

usage() {
  cat <<EOF
Usage:
  ./supervisor.sh [--cmd "<command>"]
  ./supervisor.sh --submit

Examples:
  ./supervisor.sh --cmd "$DEFAULT_CMD"
  ./supervisor.sh --submit

Alias:
  alias gym-done='./supervisor.sh --submit'
EOF
}

main() {
  if [[ -f "$LOCK_FILE" ]]; then
    echo "Lock file exists: $LOCK_FILE"
    echo "Another supervisor run may still be active."
    exit 1
  fi
  trap 'rm -f "$LOCK_FILE"' EXIT
  : >"$LOCK_FILE"

  local cmd="$DEFAULT_CMD"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --cmd)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --cmd"; exit 2; }
        cmd="$1"
        ;;
      --submit)
        submit_flow
        return
        ;;
      -h|--help)
        usage
        return
        ;;
      *)
        echo "Unknown arg: $1"
        usage
        exit 2
        ;;
    esac
    shift
  done

  run_wrapped_command "$cmd"
}

main "$@"
