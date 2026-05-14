"""
gym_watcher.py — watches solution_log.json → regenerates dashboard.html

Usage: python gym_watcher.py <problem_dir>
"""

import json
import logging
import logging.handlers
import os
import platform
import sys
import time
import webbrowser
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("[gym_watcher] 'watchdog' not installed. Run: pip install watchdog>=4.0", flush=True)
    sys.exit(1)

SOLUTION_LOG = "solution_log.json"
DASHBOARD_HTML = "dashboard.html"
LOCK_FILE = ".gym_watcher.lock"
LOG_FILE = ".gym_watcher.log"
DEBOUNCE_SECONDS = 2.0

EMPTY_SCAFFOLD = '{"version": "1.0", "problem": "", "problem_type": "mle", "prompts": []}\n'


def _pid_alive(pid: int) -> bool:
    try:
        if platform.system() == "Windows":
            import subprocess
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5
            )
            return str(pid) in r.stdout
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False


def _generate_dashboard(data: dict) -> str:
    problem = data.get("problem") or "AI Coding Gym"
    ptype = data.get("problem_type", "mle").upper()
    prompts = data.get("prompts", [])

    # Build JS-safe JSON embed
    data_json = json.dumps(data, ensure_ascii=False)

    # Build prompt labels and accuracy arrays for Chart.js
    labels = []
    accuracies = []
    for p in prompts:
        idx = p.get("prompt_index", "?")
        labels.append(f"Prompt {idx}")
        acc = p.get("accuracy")
        accuracies.append(acc)  # None becomes null in JS via json.dumps

    labels_json = json.dumps(labels)
    accuracies_json = json.dumps(accuracies)

    has_prompts = len(prompts) > 0
    has_cells = has_prompts and any(p.get("cells") for p in prompts)

    # Build prompt selector buttons (no backslash in f-string for Python <3.12)
    if has_prompts:
        btns = []
        for i, p in enumerate(prompts):
            idx = p.get("prompt_index", i + 1)
            btns.append(
                f'<button class="prompt-btn" onclick="selectPrompt({i})">Prompt {idx}</button>'
            )
        prompt_selector_html = (
            '<div class="card"><h2>Prompts</h2>'
            '<div class="prompt-selector">' + "".join(btns) + "</div></div>"
        )
    else:
        prompt_selector_html = ""

    chart_section = ""
    if has_prompts:
        chart_section = f"""
        <div class="card" id="chart-card">
          <canvas id="acc-chart" height="80"></canvas>
        </div>
        <script>
          (function() {{
            var ctx = document.getElementById('acc-chart').getContext('2d');
            var labels = {labels_json};
            var accs = {accuracies_json};
            var chart = new Chart(ctx, {{
              type: 'line',
              data: {{
                labels: labels,
                datasets: [{{
                  label: 'Accuracy',
                  data: accs,
                  borderColor: '#6366f1',
                  backgroundColor: 'rgba(99,102,241,0.15)',
                  pointBackgroundColor: '#6366f1',
                  pointRadius: 6,
                  pointHoverRadius: 9,
                  spanGaps: false,
                  tension: 0.3,
                  fill: true
                }}]
              }},
              options: {{
                responsive: true,
                onClick: function(evt, elements) {{
                  if (elements && elements.length > 0) {{
                    selectPrompt(elements[0].index);
                  }}
                }},
                scales: {{
                  y: {{
                    min: 0, max: 1,
                    ticks: {{
                      color: '#8b8fa8',
                      callback: function(v) {{ return (v*100).toFixed(0)+'%'; }}
                    }},
                    grid: {{ color: '#2d3148' }}
                  }},
                  x: {{
                    ticks: {{ color: '#8b8fa8' }},
                    grid: {{ color: '#2d3148' }}
                  }}
                }},
                plugins: {{
                  legend: {{ display: false }},
                  tooltip: {{
                    callbacks: {{
                      label: function(ctx) {{
                        var v = ctx.parsed.y;
                        return v !== null ? (v*100).toFixed(2)+'%' : 'N/A';
                      }}
                    }}
                  }}
                }}
              }}
            }});
          }})();
        </script>
"""
    else:
        chart_section = """
        <div class="card empty-state">
          <p>No data yet &mdash; waiting for the AI agent to write the first entry to <code>solution_log.json</code>.</p>
        </div>
"""

    cells_section = ""
    if has_cells:
        cells_section = """
        <div class="card" id="cells-card">
          <h2>Cell Breakdown</h2>
          <div id="cells-content"></div>
        </div>
"""

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="10">
<title>AI Coding Gym &mdash; {problem}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
:root {{
  --bg: #0f1117;
  --surface: #1a1d27;
  --surface2: #22263a;
  --border: #2d3148;
  --text: #e2e4f0;
  --muted: #8b8fa8;
  --accent: #6366f1;
  --accent2: #818cf8;
  --changed: #f59e0b;
  --changed-bg: rgba(245,158,11,0.10);
  --green: #22c55e;
  --radius: 10px;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px;
  line-height: 1.6;
  padding: 24px;
  max-width: 1100px;
  margin: 0 auto;
}}
header {{
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}}
header h1 {{
  font-size: 20px;
  font-weight: 600;
  color: var(--text);
}}
.badge {{
  background: var(--accent);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 99px;
  letter-spacing: .5px;
  text-transform: uppercase;
}}
.muted {{ color: var(--muted); font-size: 12px; margin-left: auto; }}
.card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 16px;
}}
.card h2 {{
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .8px;
  color: var(--muted);
  margin-bottom: 14px;
}}
.empty-state {{
  text-align: center;
  color: var(--muted);
  padding: 48px 20px;
}}
.empty-state code {{
  background: var(--surface2);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  color: var(--accent2);
}}
#prompt-panel {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}}
@media (max-width: 700px) {{
  #prompt-panel {{ grid-template-columns: 1fr; }}
}}
.model-badge {{
  display: inline-block;
  background: var(--accent);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 6px;
  margin-bottom: 12px;
}}
.hyperparam-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}}
.hyperparam-table td {{
  padding: 5px 8px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}}
.hyperparam-table td:first-child {{
  color: var(--muted);
  width: 45%;
  font-family: monospace;
}}
.summary-text {{
  color: var(--text);
  line-height: 1.7;
  font-size: 14px;
  white-space: pre-wrap;
}}
.traj-text {{
  color: var(--muted);
  line-height: 1.7;
  font-size: 13px;
  white-space: pre-wrap;
}}
.prompt-selector {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
}}
.prompt-btn {{
  background: var(--surface2);
  border: 1px solid var(--border);
  color: var(--muted);
  padding: 4px 12px;
  border-radius: 99px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: all .15s;
}}
.prompt-btn:hover, .prompt-btn.active {{
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}}
details {{
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;
}}
summary {{
  padding: 10px 14px;
  cursor: pointer;
  background: var(--surface2);
  font-size: 13px;
  font-weight: 500;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 8px;
  user-select: none;
}}
summary::-webkit-details-marker {{ display: none; }}
summary::before {{
  content: '▶';
  font-size: 10px;
  color: var(--muted);
  transition: transform .2s;
}}
details[open] summary::before {{ transform: rotate(90deg); }}
.cell-idx {{
  font-size: 11px;
  color: var(--muted);
  background: var(--border);
  padding: 2px 6px;
  border-radius: 4px;
}}
.lines-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}}
.lines-table th {{
  padding: 6px 8px;
  text-align: left;
  color: var(--muted);
  border-bottom: 1px solid var(--border);
  font-weight: 500;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .5px;
}}
.lines-table td {{
  padding: 5px 8px;
  border-bottom: 1px solid rgba(45,49,72,.5);
  vertical-align: top;
}}
.lines-table tr.changed-row td {{
  background: var(--changed-bg);
}}
.line-content {{
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  color: #c4c8e8;
  white-space: pre-wrap;
  word-break: break-all;
}}
.line-num {{ color: var(--muted); text-align: right; width: 36px; }}
.ai-sum {{ color: var(--text); }}
.changed-badge {{
  background: var(--changed);
  color: #000;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 4px;
  white-space: nowrap;
}}
.change-reason-row td {{
  background: rgba(245,158,11,0.06) !important;
  color: var(--changed);
  font-size: 12px;
  padding: 4px 8px 8px 8px;
  border-bottom: 1px solid var(--border) !important;
}}
</style>
</head>
<body>

<script>
const GYM_DATA = {data_json};
let selectedIdx = null;

function selectPrompt(idx) {{
  selectedIdx = idx;
  document.querySelectorAll('.prompt-btn').forEach(function(b, i) {{
    b.classList.toggle('active', i === idx);
  }});
  renderPanel(idx);
}}

function renderPanel(idx) {{
  var p = GYM_DATA.prompts[idx];
  if (!p) return;

  // model + hyperparams
  var modelDiv = document.getElementById('model-info');
  if (modelDiv) {{
    var m = p.model;
    if (m && m.name) {{
      var hp = m.hyperparams || {{}};
      var rows = Object.entries(hp).map(function(kv) {{
        return '<tr><td>' + escHtml(kv[0]) + '</td><td>' + escHtml(String(kv[1])) + '</td></tr>';
      }}).join('');
      modelDiv.innerHTML =
        '<div class="model-badge">' + escHtml(m.name) + '</div>' +
        (rows ? '<table class="hyperparam-table"><tbody>' + rows + '</tbody></table>' : '');
    }} else {{
      modelDiv.innerHTML = '<span style="color:var(--muted)">No model recorded for this prompt.</span>';
    }}
  }}

  // accuracy
  var accEl = document.getElementById('acc-value');
  if (accEl) {{
    var acc = p.accuracy;
    accEl.textContent = acc !== null && acc !== undefined
      ? (acc * 100).toFixed(2) + '%'
      : 'N/A';
    accEl.style.color = acc !== null ? 'var(--green)' : 'var(--muted)';
  }}

  // approach
  var approachEl = document.getElementById('approach-text');
  if (approachEl) {{
    approachEl.textContent = p.approach_summary || '—';
  }}

  // trajectory
  var trajEl = document.getElementById('traj-text');
  if (trajEl) {{
    trajEl.textContent = p.trajectory_summary || '—';
  }}

  // user prompt
  var upEl = document.getElementById('user-prompt-text');
  if (upEl) {{
    upEl.textContent = p.user_prompt || '';
  }}

  // cells
  renderCells(p);
}}

function renderCells(p) {{
  var container = document.getElementById('cells-content');
  if (!container) return;
  var cells = p.cells || [];
  if (!cells.length) {{
    container.innerHTML = '<p style="color:var(--muted)">No cell data for this prompt.</p>';
    return;
  }}
  var html = '';
  cells.forEach(function(cell) {{
    if (cell.cell_type === 'markdown') return;
    var lines = cell.lines || [];
    var rows = lines.map(function(ln) {{
      var changed = ln.changed;
      var rowClass = changed ? 'changed-row' : '';
      var badge = changed ? '<span class="changed-badge">changed</span>' : '';
      var mainRow =
        '<tr class="' + rowClass + '">' +
          '<td class="line-num">' + ln.line_index + '</td>' +
          '<td class="line-content">' + escHtml(ln.content || '') + '</td>' +
          '<td class="ai-sum">' + escHtml(ln.ai_summary || '') + '</td>' +
          '<td>' + badge + '</td>' +
        '</tr>';
      var reasonRow = '';
      if (changed && ln.change_reason) {{
        reasonRow =
          '<tr class="change-reason-row">' +
            '<td></td>' +
            '<td colspan="3">↳ ' + escHtml(ln.change_reason) + '</td>' +
          '</tr>';
      }}
      return mainRow + reasonRow;
    }}).join('');

    html +=
      '<details>' +
        '<summary>' +
          '<span class="cell-idx">cell ' + cell.cell_index + '</span>' +
          escHtml(cell.cell_summary || 'Code cell') +
        '</summary>' +
        '<div style="overflow-x:auto;">' +
          '<table class="lines-table">' +
            '<thead><tr>' +
              '<th style="width:40px">#</th>' +
              '<th>Source</th>' +
              '<th>AI Summary</th>' +
              '<th style="width:70px">Status</th>' +
            '</tr></thead>' +
            '<tbody>' + rows + '</tbody>' +
          '</table>' +
        '</div>' +
      '</details>';
  }});
  container.innerHTML = html || '<p style="color:var(--muted)">No code cells.</p>';
}}

function escHtml(s) {{
  return String(s)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}}

window.addEventListener('DOMContentLoaded', function() {{
  // default: last prompt with non-null accuracy
  var prompts = GYM_DATA.prompts || [];
  var def = prompts.length - 1;
  for (var i = prompts.length - 1; i >= 0; i--) {{
    if (prompts[i].accuracy !== null && prompts[i].accuracy !== undefined) {{
      def = i; break;
    }}
  }}
  if (def >= 0) selectPrompt(def);
}});
</script>

<header>
  <h1>{problem}</h1>
  <span class="badge">{ptype}</span>
  <span class="muted" id="ts-label">dashboard</span>
</header>

{"" if has_prompts else ""}

<!-- prompt selector -->
{prompt_selector_html}

{chart_section}

{"" if not has_prompts else """
<div id="prompt-panel">
  <div class="card">
    <h2>Model &amp; Hyperparameters</h2>
    <div style="margin-bottom:10px">
      <span style="color:var(--muted);font-size:12px">Accuracy: </span>
      <span id="acc-value" style="font-size:20px;font-weight:700"></span>
    </div>
    <div id="model-info"></div>
  </div>
  <div class="card">
    <h2>User Prompt</h2>
    <p id="user-prompt-text" class="traj-text"></p>
  </div>
</div>

<div class="card">
  <h2>Approach Summary</h2>
  <p id="approach-text" class="summary-text"></p>
</div>

<div class="card">
  <h2>Trajectory Summary</h2>
  <p id="traj-text" class="traj-text"></p>
</div>
"""}

{cells_section}

</body>
</html>"""

    return html


def _regenerate(log_path: Path, dash_path: Path, logger: logging.Logger) -> None:
    try:
        raw = log_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("JSON parse failed: %s — leaving dashboard unchanged", e)
        return
    except OSError as e:
        logger.error("Could not read %s: %s", log_path, e)
        return

    try:
        html = _generate_dashboard(data)
    except Exception as e:
        logger.error("Dashboard generation error: %s", e, exc_info=True)
        return

    tmp = dash_path.with_suffix(".tmp")
    try:
        tmp.write_text(html, encoding="utf-8")
        tmp.replace(dash_path)
        n = len(data.get("prompts", []))
        logger.info("Dashboard updated (%d prompt%s)", n, "" if n == 1 else "s")
    except OSError as e:
        logger.error("Could not write dashboard: %s", e)


class _Handler(FileSystemEventHandler):
    def __init__(self, log_path: Path, dash_path: Path, logger: logging.Logger):
        self._log_path = log_path
        self._dash_path = dash_path
        self._logger = logger
        self._last_fire = 0.0

    def on_modified(self, event):
        self._check(event)

    def on_created(self, event):
        self._check(event)

    def _check(self, event):
        if event.is_directory:
            return
        p = Path(event.src_path)
        if p.name != SOLUTION_LOG:
            return
        now = time.time()
        if now - self._last_fire < DEBOUNCE_SECONDS:
            return
        self._last_fire = now
        self._logger.info("Detected change in %s", SOLUTION_LOG)
        _regenerate(self._log_path, self._dash_path, self._logger)


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: python gym_watcher.py <problem_dir>", file=sys.stderr)
        sys.exit(1)

    problem_dir = Path(sys.argv[1]).resolve()
    if not problem_dir.is_dir():
        print(f"[gym_watcher] Not a directory: {problem_dir}", file=sys.stderr)
        sys.exit(1)

    # Logging setup
    log_path = problem_dir / LOG_FILE
    logger = logging.getLogger("gym_watcher")
    logger.setLevel(logging.INFO)
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    stdout_h = logging.StreamHandler(sys.stdout)
    stdout_h.setFormatter(logging.Formatter("[gym_watcher] %(message)s"))
    logger.addHandler(stdout_h)

    # Single-instance check
    lock = problem_dir / LOCK_FILE
    if lock.exists():
        try:
            pid = int(lock.read_text(encoding="utf-8").strip())
            if _pid_alive(pid):
                logger.info("Already running (PID %d). Exiting.", pid)
                sys.exit(0)
        except (OSError, ValueError):
            pass
        try:
            lock.unlink()
        except OSError:
            pass

    lock.write_text(str(os.getpid()), encoding="utf-8")

    solution_log = problem_dir / SOLUTION_LOG
    dashboard = problem_dir / DASHBOARD_HTML

    # Seed empty scaffold if absent
    if not solution_log.exists():
        solution_log.write_text(EMPTY_SCAFFOLD, encoding="utf-8")
        logger.info("Created empty %s", SOLUTION_LOG)

    # Initial render
    _regenerate(solution_log, dashboard, logger)

    # Open browser
    try:
        webbrowser.open(dashboard.as_uri())
        logger.info("Opened dashboard in browser")
    except Exception:
        logger.info("Dashboard: %s", dashboard)

    # Start watchdog
    event_handler = _Handler(solution_log, dashboard, logger)
    observer = Observer()
    observer.schedule(event_handler, str(problem_dir), recursive=False)
    observer.start()
    logger.info("Watching %s", solution_log)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        try:
            lock.unlink()
        except OSError:
            pass
        logger.info("Stopped.")


if __name__ == "__main__":
    main()
