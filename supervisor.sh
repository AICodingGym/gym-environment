#!/usr/bin/env bash
# AI Coding Gym supervisor: watches the problem folder, appends compact
# activity cards to dashboard.html, and auto-runs the notebook metric
# extractor whenever files change.
#
# Design goals:
#   * Zero external deps beyond coreutils + diff + python (rsync optional).
#   * Compact dashboard: per-file +/- summary up front, full diffs hidden
#     behind <details>, notebooks never dumped as raw JSON, binary files
#     reported by name only.
#   * First run after fetch shows a "Supervisor Ready" card, never the
#     entire workspace as a "+everything" diff.
#   * Idempotent: re-running is safe; the lock file prevents doubles.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_PATH="$ROOT_DIR/dashboard.html"
NOTEBOOK_PATH="$ROOT_DIR/solution.ipynb"
SNAPSHOT_DIR="$ROOT_DIR/.supervisor_snapshot"
LOCK_FILE="$ROOT_DIR/.supervisor.lock"
HELPER="$ROOT_DIR/tools/notebook_metrics.py"
DEFAULT_CMD="aicodinggym mle log show <competition_or_problem_id>"
SUBMIT_CMD="aicodinggym mle submit <competition_or_problem_id> -F submission.csv"
WATCH_INTERVAL=3
MAX_DIFF_LINES_PER_FILE=200
MAX_OUTPUT_LINES=200

timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

html_escape() {
  sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

PY_BIN="${PYTHON:-python}"
command -v "$PY_BIN" >/dev/null 2>&1 || PY_BIN=python3

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
  <title>AI Coding Gym Supervisor</title>
  <style>
    :root { color-scheme: dark; --bg:#0b0e14; --panel:#131822; --card:#1a2030; --border:#2a3446; --text:#e6edf3; --muted:#8b98aa; --accent:#58a6ff; --plus:#56d364; --minus:#ff7b72; }
    * { box-sizing: border-box; }
    body { font-family: ui-sans-serif, Inter, Segoe UI, Arial, sans-serif; margin: 0; background: var(--bg); color: var(--text); }
    header { position: sticky; top: 0; z-index: 10; background: rgba(11,14,20,0.9); backdrop-filter: blur(8px); border-bottom: 1px solid var(--border); padding: 14px 24px; display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
    header h1 { margin: 0; font-size: 18px; font-weight: 600; }
    .stat { display: flex; flex-direction: column; gap: 2px; }
    .stat .label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; }
    .stat .value { font-size: 16px; font-weight: 600; font-variant-numeric: tabular-nums; }
    .stat .value.accent { color: var(--accent); }
    main { max-width: 1080px; margin: 0 auto; padding: 20px 24px 40px; }
    .panel { border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px; margin-bottom: 20px; background: var(--panel); }
    .panel h2 { margin: 0 0 8px; font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; }
    #metricChart { width: 100%; height: 180px; display: block; }
    .card { border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; margin-bottom: 12px; background: var(--card); }
    .card .row { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
    .card h3 { margin: 0; font-size: 14px; font-weight: 600; }
    .card .time { color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
    .card .meta { color: var(--muted); font-size: 12px; margin: 6px 0 0; word-break: break-word; }
    .card .meta code { background: rgba(255,255,255,0.05); padding: 1px 6px; border-radius: 4px; color: #a8c6ff; font-size: 11.5px; }
    details { margin-top: 8px; }
    details summary { cursor: pointer; color: var(--muted); font-size: 12px; user-select: none; padding: 4px 0; }
    details summary:hover { color: var(--text); }
    details[open] summary { color: var(--text); margin-bottom: 4px; }
    pre { white-space: pre-wrap; margin: 0; font-size: 11.5px; line-height: 1.45; font-family: ui-monospace, Menlo, Consolas, monospace; overflow-x: auto; background: rgba(0,0,0,0.25); border-radius: 6px; padding: 10px 12px; border: 1px solid rgba(255,255,255,0.04); }
    .plus { color: var(--plus); }
    .minus { color: var(--minus); }
    .pill { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
    .pill.ok { background: rgba(86,211,100,0.15); color: var(--plus); }
    .pill.fail { background: rgba(255,123,114,0.15); color: var(--minus); }
    .pill.info { background: rgba(88,166,255,0.15); color: var(--accent); }
    .empty { color: var(--muted); font-size: 12px; padding: 8px 4px; }
  </style>
</head>
<body>
  <header>
    <h1>AI Coding Gym Supervisor</h1>
    <div class="stat"><span class="label">Latest metric</span><span class="value accent" id="latestMetric">—</span></div>
    <div class="stat"><span class="label">Updated</span><span class="value" id="latestTime">—</span></div>
    <div class="stat"><span class="label">Cards</span><span class="value" id="cardCount">0</span></div>
  </header>
  <main>
    <div class="panel">
      <h2>Metric trend (<span id="metricDirection">higher is better</span>)</h2>
      <svg id="metricChart" viewBox="0 0 1000 180" preserveAspectRatio="none"></svg>
    </div>
    <div id="cards"></div>
  </main>
  <script>
    (function () {
      const cards = Array.from(document.querySelectorAll("#cards .card"));
      document.getElementById("cardCount").textContent = cards.length;
      const metricCards = cards.filter((c) => c.hasAttribute("data-metric"));
      const values = metricCards.map((c) => Number(c.getAttribute("data-metric"))).filter(Number.isFinite);
      const svg = document.getElementById("metricChart");
      const latestEl = document.getElementById("latestMetric");
      const latestTimeEl = document.getElementById("latestTime");
      if (cards.length) {
        const t = cards[cards.length - 1].querySelector(".time");
        if (t) latestTimeEl.textContent = t.textContent;
      }
      if (!values.length) {
        svg.innerHTML = '<text x="20" y="30" fill="#8b98aa" font-size="12">No metric values yet. Add a VAL_ACC: line to your notebook.</text>';
        return;
      }
      latestEl.textContent = values[values.length - 1].toFixed(4);
      const w = 1000, h = 180, p = 16;
      const min = Math.min(...values), max = Math.max(...values);
      const span = (max - min) || 1;
      const pts = values.map((v, i) => {
        const x = p + (i * (w - 2 * p) / Math.max(values.length - 1, 1));
        const y = h - p - ((v - min) / span) * (h - 2 * p);
        return `${x},${y}`;
      });
      svg.innerHTML =
        `<polyline fill="none" stroke="#58a6ff" stroke-width="2.5" stroke-linejoin="round" points="${pts.join(" ")}" />` +
        pts.map((p) => { const [x,y]=p.split(","); return `<circle cx="${x}" cy="${y}" r="3" fill="#58a6ff" />`; }).join("");
    })();
  </script>
</body>
</html>
EOF
}

append_card() {
  # Args: title, meta_html, body_html, metric_value (optional)
  local title="$1"
  local meta="$2"
  local body_html="$3"
  local metric="${4:-}"
  local temp_file
  temp_file="$(mktemp)"
  PYTHONIOENCODING=utf-8 PYTHONUTF8=1 "$PY_BIN" - "$DASHBOARD_PATH" "$title" "$meta" "$metric" <<'PY' "$body_html" >"$temp_file"
import sys, pathlib, datetime
dash_path, title, meta, metric, body = sys.argv[1:6]
src = pathlib.Path(dash_path).read_text(encoding="utf-8")
anchor = '<div id="cards">'
idx = src.find(anchor)
out = src
if idx != -1:
    insert_at = idx + len(anchor)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    attr = f' data-metric="{metric}"' if metric else ''
    card_lines = [f'\n      <div class="card"{attr}>']
    card_lines.append(f'        <div class="row"><h3>{title}</h3><span class="time">{ts}</span></div>')
    if meta:
        card_lines.append(f'        <div class="meta">{meta}</div>')
    card_lines.append(body)
    card_lines.append('      </div>')
    out = src[:insert_at] + "\n".join(card_lines) + src[insert_at:]
# Always force utf-8 bytes to stdout so non-ASCII chars survive round-tripping on Windows.
sys.stdout.buffer.write(out.encode("utf-8"))
PY
  mv "$temp_file" "$DASHBOARD_PATH"
}

snapshot_workspace() {
  rm -rf "$SNAPSHOT_DIR"
  mkdir -p "$SNAPSHOT_DIR"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude ".git" \
      --exclude ".supervisor_snapshot" \
      --exclude ".supervisor.lock" \
      --exclude "dashboard.html" \
      "$ROOT_DIR/" "$SNAPSHOT_DIR/"
    return
  fi
  # Portable fallback when rsync is missing (e.g. Git Bash on Windows).
  (
    cd "$ROOT_DIR"
    find . \
      -path ./.git -prune -o \
      -path ./.supervisor_snapshot -prune -o \
      -name .supervisor.lock -prune -o \
      -name dashboard.html -prune -o \
      -print0 |
      while IFS= read -r -d '' path; do
        [[ "$path" == "." ]] && continue
        dest="$SNAPSHOT_DIR/${path#./}"
        if [[ -d "$path" ]]; then
          mkdir -p "$dest"
        else
          mkdir -p "$(dirname "$dest")"
          cp -a "$path" "$dest"
        fi
      done
  )
}

# Builds a compact list of changed files and an optional collapsed <details>
# with the full diff. Notebooks and binaries get summarized, not dumped.
render_change_card_body() {
  local body_file
  body_file="$(mktemp)"
  PYTHONIOENCODING=utf-8 PYTHONUTF8=1 "$PY_BIN" - "$SNAPSHOT_DIR" "$ROOT_DIR" "$MAX_DIFF_LINES_PER_FILE" >"$body_file" <<'PY'
import difflib, html, os, sys, pathlib, filecmp

snap, root, max_lines = sys.argv[1], sys.argv[2], int(sys.argv[3])
SKIP_DIRS = {".git", ".supervisor_snapshot", "__pycache__"}
SKIP_NAMES = {".supervisor.lock", "dashboard.html"}
BINARY_SUFFIXES = {".zip", ".gz", ".tar", ".pkl", ".joblib", ".npy", ".npz", ".parquet", ".pt", ".pth", ".bin", ".onnx", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".csv", ".xls", ".xlsx"}

def walk(base):
    files = {}
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name in SKIP_NAMES:
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, base).replace(os.sep, "/")
            try:
                files[rel] = os.path.getsize(full)
            except OSError:
                pass
    return files

snap_files = walk(snap) if os.path.isdir(snap) else {}
root_files = walk(root)

def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines(keepends=False)
    except (OSError, UnicodeDecodeError):
        return None

def classify(rel):
    suf = pathlib.PurePosixPath(rel).suffix.lower()
    if suf == ".ipynb":
        return "notebook"
    if suf in BINARY_SUFFIXES:
        return "binary"
    return "text"

changes = []  # list of (status, rel, added, removed, diff_html)
all_rels = sorted(set(snap_files) | set(root_files))
for rel in all_rels:
    in_snap = rel in snap_files
    in_root = rel in root_files
    snap_path = os.path.join(snap, rel)
    root_path = os.path.join(root, rel)
    if in_snap and in_root:
        # Quick shallow check.
        try:
            if filecmp.cmp(snap_path, root_path, shallow=False):
                continue
        except OSError:
            pass
        status = "modified"
    elif in_root:
        status = "added"
    else:
        status = "removed"

    kind = classify(rel)
    added = removed = 0
    diff_html = ""

    if kind == "notebook":
        # Avoid dumping JSON; just say "notebook changed" with byte delta.
        s1 = snap_files.get(rel, 0)
        s2 = root_files.get(rel, 0)
        diff_html = f'<pre>notebook {status} (size {s1} \u2192 {s2} bytes)</pre>'
    elif kind == "binary":
        s1 = snap_files.get(rel, 0)
        s2 = root_files.get(rel, 0)
        diff_html = f'<pre>binary {status} (size {s1} \u2192 {s2} bytes)</pre>'
    else:
        a = read_text(snap_path) if in_snap else []
        b = read_text(root_path) if in_root else []
        if a is None or b is None:
            diff_html = f'<pre>{status} (not UTF-8 readable)</pre>'
        else:
            diff_lines = list(difflib.unified_diff(a, b, fromfile=f"a/{rel}", tofile=f"b/{rel}", lineterm=""))
            for ln in diff_lines:
                if ln.startswith("+") and not ln.startswith("+++"):
                    added += 1
                elif ln.startswith("-") and not ln.startswith("---"):
                    removed += 1
            if len(diff_lines) > max_lines:
                truncated = diff_lines[:max_lines]
                truncated.append(f"... ({len(diff_lines) - max_lines} more lines)")
                diff_lines = truncated
            rendered = []
            for ln in diff_lines:
                esc = html.escape(ln)
                if ln.startswith("+") and not ln.startswith("+++"):
                    rendered.append(f'<span class="plus">{esc}</span>')
                elif ln.startswith("-") and not ln.startswith("---"):
                    rendered.append(f'<span class="minus">{esc}</span>')
                else:
                    rendered.append(esc)
            body = "\n".join(rendered) if rendered else "(no textual diff)"
            diff_html = f'<pre>{body}</pre>'

    changes.append((status, rel, added, removed, diff_html))

if not changes:
    print('        <div class="empty">No file changes detected.</div>')
    sys.exit(0)

# Summary line: N files, +X / -Y
total_added = sum(c[2] for c in changes)
total_removed = sum(c[3] for c in changes)
summary = f'{len(changes)} file{"s" if len(changes)!=1 else ""} changed, <span class="plus">+{total_added}</span> / <span class="minus">-{total_removed}</span>'
print(f'        <div class="meta">{summary}</div>')

# Collapsed list of per-file diffs.
print('        <details>')
print('          <summary>Show per-file diffs</summary>')
for status, rel, added, removed, diff_html in changes:
    badge = {"added":"<span class=\"pill ok\">added</span>", "removed":"<span class=\"pill fail\">removed</span>", "modified":"<span class=\"pill info\">modified</span>"}[status]
    header = f'{badge} <code>{html.escape(rel)}</code>'
    if added or removed:
        header += f' <span class="plus">+{added}</span> / <span class="minus">-{removed}</span>'
    print('          <details>')
    print(f'            <summary>{header}</summary>')
    print(f'            {diff_html}')
    print('          </details>')
print('        </details>')
PY
  cat "$body_file"
  rm -f "$body_file"
}

run_notebook_and_log_metric() {
  if [[ ! -f "$NOTEBOOK_PATH" ]]; then
    append_card "Notebook Metric" "No <code>solution.ipynb</code> found yet" '        <div class="empty">Create solution.ipynb to enable automatic metric extraction.</div>'
    return
  fi
  local output status max_acc
  set +e
  output="$("$PY_BIN" "$HELPER" "$NOTEBOOK_PATH" 2>&1)"
  status=$?
  set -e
  max_acc="$(printf "%s\n" "$output" | grep -oE 'MAX_VALIDATION_ACCURACY=[^[:space:]]+' | tail -n1 | cut -d= -f2 || true)"
  [[ -z "${max_acc:-}" ]] && max_acc="NA"
  # Tail the output to keep the card compact.
  local tail_output
  tail_output="$(printf "%s\n" "$output" | tail -n "$MAX_OUTPUT_LINES")"
  local body
  body="$(printf '        <details>\n          <summary>Show notebook output (last %d lines)</summary>\n          <pre>%s</pre>\n        </details>' \
    "$MAX_OUTPUT_LINES" \
    "$(printf "%s" "$tail_output" | html_escape)")"
  local pill
  if [[ "$status" -eq 0 ]]; then
    pill='<span class="pill ok">ok</span>'
  else
    pill='<span class="pill fail">exit '"$status"'</span>'
  fi
  local meta
  if [[ "$max_acc" == "NA" ]]; then
    meta="$pill <code>MAX_VALIDATION_ACCURACY=NA</code> \u2013 add <code>VAL_ACC: &lt;float&gt;</code> or <code>validation_accuracy: &lt;float&gt;</code> in your notebook"
    append_card "Notebook Metric" "$meta" "$body"
  else
    meta="$pill <code>MAX_VALIDATION_ACCURACY=$max_acc</code>"
    append_card "Notebook Metric" "$meta" "$body" "$max_acc"
  fi
}

run_wrapped_command() {
  local command="$1"
  ensure_dashboard
  snapshot_workspace

  local command_output status
  set +e
  command_output="$(bash -lc "$command" 2>&1)"
  status=$?
  set -e

  sleep 1
  local body meta pill
  body="$(render_change_card_body)"
  if [[ "$status" -eq 0 ]]; then
    pill='<span class="pill ok">ok</span>'
  else
    pill='<span class="pill fail">exit '"$status"'</span>'
  fi
  meta="$pill <code>$(printf "%s" "$command" | html_escape)</code>"
  append_card "AI Run" "$meta" "$body"

  local tail_output
  tail_output="$(printf "%s\n" "$command_output" | tail -n "$MAX_OUTPUT_LINES")"
  local output_body
  output_body="$(printf '        <details>\n          <summary>Show command output (last %d lines)</summary>\n          <pre>%s</pre>\n        </details>' \
    "$MAX_OUTPUT_LINES" \
    "$(printf "%s" "$tail_output" | html_escape)")"
  append_card "Command Output" "" "$output_body"

  run_notebook_and_log_metric
}

watch_loop() {
  ensure_dashboard
  local first_run=0
  if [[ ! -d "$SNAPSHOT_DIR" ]]; then
    first_run=1
  fi
  snapshot_workspace
  if [[ "$first_run" -eq 1 ]]; then
    append_card "Supervisor Ready" "<span class=\"pill info\">watching</span> interval=${WATCH_INTERVAL}s \u2013 edits you make will appear below" '        <div class="empty">No changes yet. Start coding\u2014each save will append a card.</div>'
  else
    append_card "Watcher Restarted" "<span class=\"pill info\">watching</span> interval=${WATCH_INTERVAL}s" '        <div class="empty">Resuming watch mode.</div>'
  fi
  while true; do
    sleep "$WATCH_INTERVAL"
    # Check whether any file actually changed before doing expensive work.
    local body
    body="$(render_change_card_body)"
    if [[ "$body" == *"No file changes detected."* ]]; then
      continue
    fi
    append_card "Change Detected" "" "$body"
    run_notebook_and_log_metric
    snapshot_workspace
  done
}

submit_flow() {
  ensure_dashboard
  local output status ground_truth
  set +e
  output="$(bash -lc "$SUBMIT_CMD" 2>&1)"
  status=$?
  set -e
  ground_truth="$(printf "%s\n" "$output" | grep -oEi 'ground[ _-]?truth[^0-9]*[0-9]+(\.[0-9]+)?' | head -n1 || true)"
  [[ -z "${ground_truth:-}" ]] && ground_truth="Ground Truth: not found in output"
  local pill
  if [[ "$status" -eq 0 ]]; then
    pill='<span class="pill ok">submitted</span>'
  else
    pill='<span class="pill fail">submit failed (exit '"$status"')</span>'
  fi
  local body
  body="$(printf '        <div class="meta">%s</div>\n        <details open>\n          <summary>Show submit log</summary>\n          <pre>%s</pre>\n        </details>' \
    "$(printf "%s" "$ground_truth" | html_escape)" \
    "$(printf "%s" "$output" | html_escape)")"
  append_card "Final Result" "$pill" "$body"
  open_dashboard
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

usage() {
  cat <<EOF
Usage:
  ./supervisor.sh --watch              # background watcher (auto-started on fetch)
  ./supervisor.sh --cmd "<command>"    # run one command and log the diff
  ./supervisor.sh --submit             # run the bound submit command
  ./supervisor.sh --open               # open dashboard.html in the browser

Examples:
  ./supervisor.sh --watch
  ./supervisor.sh --cmd "$DEFAULT_CMD"
  ./supervisor.sh --submit
EOF
}

main() {
  if [[ -f "$LOCK_FILE" ]]; then
    local pid
    pid="$(cat "$LOCK_FILE" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "Supervisor already running (pid $pid). Remove $LOCK_FILE if this is stale."
      exit 1
    fi
    rm -f "$LOCK_FILE"
  fi
  trap 'rm -f "$LOCK_FILE"' EXIT
  echo "$$" >"$LOCK_FILE"

  local mode="watch"
  local cmd="$DEFAULT_CMD"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --watch) mode="watch" ;;
      --cmd)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --cmd"; exit 2; }
        mode="cmd"
        cmd="$1"
        ;;
      --submit) mode="submit" ;;
      --open) mode="open" ;;
      --interval) shift; WATCH_INTERVAL="${1:-3}" ;;
      -h|--help) usage; return ;;
      *) echo "Unknown arg: $1"; usage; exit 2 ;;
    esac
    shift
  done

  ensure_dashboard
  case "$mode" in
    watch) watch_loop ;;
    cmd) run_wrapped_command "$cmd" ;;
    submit) submit_flow ;;
    open) open_dashboard ;;
  esac
}

main "$@"
