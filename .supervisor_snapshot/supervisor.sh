#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_PATH="$ROOT_DIR/dashboard.html"
NOTEBOOK_PATH="$ROOT_DIR/solution.ipynb"
SNAPSHOT_DIR="$ROOT_DIR/.supervisor_snapshot"
LOCK_FILE="$ROOT_DIR/.supervisor.lock"
HELPER="$ROOT_DIR/tools/notebook_metrics.py"

DEFAULT_CMD="aicodinggym mle log show <problem-id>"
SUBMIT_CMD="echo \"Set submit command for this challenge type\""
DEFAULT_ACTOR="ai"
DEFAULT_NOTE="automated run"

timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

html_escape() {
  sed \
    -e 's/&/\&amp;/g' \
    -e 's/</\&lt;/g' \
    -e 's/>/\&gt;/g'
}

open_dashboard() {
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$DASHBOARD_PATH" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$DASHBOARD_PATH" >/dev/null 2>&1 || true
  elif command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command "Start-Process '$DASHBOARD_PATH'" >/dev/null 2>&1 || true
  fi
}

append_card() {
  local title="$1"
  local meta="$2"
  local body_html="$3"
  local attrs="${4:-}"
  local temp_file
  temp_file="$(mktemp)"
  awk '
    /<\/body>/ { exit }
    { print }
  ' "$DASHBOARD_PATH" >"$temp_file"
  {
    printf '<div class="card"%s>\n' "$attrs"
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
  local actor="$1"
  local note="$2"
  if [[ ! -f "$NOTEBOOK_PATH" ]]; then
    append_card "Notebook Automation" "Notebook missing" "<pre>Expected $NOTEBOOK_PATH</pre>" \
      " data-kind=\"metric\" data-ts=\"$(timestamp)\" data-val=\"\" data-actor=\"${actor}\" data-note=\"${note}\""
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
  append_card \
    "Notebook Automation" \
    "actor: ${actor} | note: ${note} | MAX_VALIDATION_ACCURACY=${max_acc} (status=${status})" \
    "<pre>${body}</pre>" \
    " data-kind=\"metric\" data-ts=\"$(timestamp)\" data-val=\"${max_acc}\" data-actor=\"${actor}\" data-note=\"${note}\""
}

run_wrapped_command() {
  local command="$1"
  local actor="$2"
  local note="$3"
  local should_open="$4"
  if [[ "$should_open" == "1" ]]; then
    open_dashboard
  fi
  snapshot_workspace

  local command_output
  set +e
  command_output="$(bash -lc "$command" 2>&1)"
  local status=$?
  set -e

  sleep 1
  local changes_html
  changes_html="$(diff_to_html)"
  append_card "Execution Interception" "actor: ${actor} | note: ${note} | command: $command (exit=${status})" "$changes_html"
  append_card "Command Output" "actor: ${actor} | note: ${note}" "<pre>$(printf "%s\n" "$command_output" | html_escape)</pre>"
  run_notebook_and_log_metric "$actor" "$note"
}

submit_flow() {
  local actor="$1"
  local note="$2"
  local should_open="$3"
  if [[ "$should_open" == "1" ]]; then
    open_dashboard
  fi
  local output
  set +e
  output="$(bash -lc "$SUBMIT_CMD" 2>&1)"
  local status=$?
  set -e

  local ground_truth
  ground_truth="$(printf "%s\n" "$output" | grep -oEi 'ground[ _-]?truth[^0-9]*[0-9]+(\.[0-9]+)?' | head -n1 || true)"
  [[ -z "${ground_truth:-}" ]] && ground_truth="Ground Truth: not found in output"
  local gt_value
  gt_value="$(printf "%s\n" "$ground_truth" | grep -oE '[0-9]+(\.[0-9]+)?' | head -n1 || true)"
  append_card \
    "Final Result" \
    "actor: ${actor} | note: ${note} | submit exit=${status}" \
    "<pre>$(printf "%s\n%s\n" "$ground_truth" "$output" | html_escape)</pre>" \
    " data-kind=\"ground_truth\" data-ts=\"$(timestamp)\" data-gt=\"${gt_value}\" data-actor=\"${actor}\" data-note=\"${note}\""
}

usage() {
  cat <<EOF
Usage:
  ./supervisor.sh [--cmd "<command>"] [--actor ai|human] [--note "prompt/intent"] [--no-open]
  ./supervisor.sh --submit [--actor ai|human] [--note "submission intent"] [--no-open]

Examples:
  ./supervisor.sh --cmd "$DEFAULT_CMD" --actor ai --note "feature iteration"
  ./supervisor.sh --submit --actor human --note "final submission"
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
  local actor="$DEFAULT_ACTOR"
  local note="$DEFAULT_NOTE"
  local should_open=1
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --cmd)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --cmd"; exit 2; }
        cmd="$1"
        ;;
      --actor)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --actor"; exit 2; }
        actor="$1"
        ;;
      --note)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --note"; exit 2; }
        note="$1"
        ;;
      --no-open)
        should_open=0
        ;;
      --submit)
        submit_flow "$actor" "$note" "$should_open"
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

  run_wrapped_command "$cmd" "$actor" "$note" "$should_open"
}

main "$@"
