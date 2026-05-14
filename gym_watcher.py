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

    data_json = json.dumps(data, ensure_ascii=False)

    labels = []
    accuracies = []
    for p in prompts:
        idx = p.get("prompt_index", "?")
        labels.append(f"Prompt {idx}")
        acc = p.get("accuracy")
        accuracies.append(acc)

    labels_json = json.dumps(labels)
    accuracies_json = json.dumps(accuracies)

    has_prompts = len(prompts) > 0
    has_cells = has_prompts and any(p.get("cells") for p in prompts)

    if has_prompts:
        btns = []
        for i, p in enumerate(prompts):
            idx = p.get("prompt_index", i + 1)
            btns.append(
                f'<button class="prompt-btn" onclick="selectPrompt({i})">Prompt {idx}</button>'
            )
        prompt_selector_html = (
            '<div class="card"><div class="card-label">Prompts</div>'
            '<div class="prompt-selector">' + "".join(btns) + "</div></div>"
        )
    else:
        prompt_selector_html = ""

    chart_section = ""
    if has_prompts:
        chart_section = f"""
        <div class="card" id="chart-card">
          <div class="card-label">Accuracy Progress</div>
          <canvas id="acc-chart" height="70"></canvas>
        </div>
        <script>
          (function() {{
            var ctx = document.getElementById('acc-chart').getContext('2d');
            var labels = {labels_json};
            var accs = {accuracies_json};

            // Dynamic Y-axis: zoom into actual accuracy range
            var validAccs = accs.filter(function(a) {{ return a !== null && a !== undefined; }});
            var yMin = 0, yMax = 1;
            if (validAccs.length > 0) {{
              var minV = Math.min.apply(null, validAccs);
              var maxV = Math.max.apply(null, validAccs);
              var spread = maxV - minV;
              var pad = Math.max(spread * 0.4, 0.002);
              yMin = Math.max(0, minV - pad);
              yMax = Math.min(1, maxV + pad);
              if (yMax - yMin < 0.004) {{
                yMin = Math.max(0, minV - 0.003);
                yMax = Math.min(1, maxV + 0.003);
              }}
            }}

            var chart = new Chart(ctx, {{
              type: 'line',
              data: {{
                labels: labels,
                datasets: [{{
                  label: 'Accuracy',
                  data: accs,
                  borderColor: '#F97316',
                  backgroundColor: 'rgba(249,115,22,0.08)',
                  pointBackgroundColor: '#F97316',
                  pointBorderColor: '#fff',
                  pointBorderWidth: 2,
                  pointRadius: 7,
                  pointHoverRadius: 10,
                  spanGaps: false,
                  tension: 0.35,
                  fill: true,
                  borderWidth: 2.5
                }}]
              }},
              options: {{
                responsive: true,
                onClick: function(evt, elements) {{
                  if (elements && elements.length > 0) selectPrompt(elements[0].index);
                }},
                scales: {{
                  y: {{
                    min: yMin,
                    max: yMax,
                    ticks: {{
                      color: '#78716C',
                      maxTicksLimit: 6,
                      callback: function(v) {{
                        var range = yMax - yMin;
                        if (range < 0.01) return (v*100).toFixed(3)+'%';
                        if (range < 0.05) return (v*100).toFixed(2)+'%';
                        if (range < 0.2)  return (v*100).toFixed(1)+'%';
                        return (v*100).toFixed(0)+'%';
                      }}
                    }},
                    grid: {{ color: 'rgba(0,0,0,0.06)' }},
                    border: {{ color: '#E7E5E4' }}
                  }},
                  x: {{
                    ticks: {{ color: '#78716C', font: {{ size: 12 }} }},
                    grid: {{ color: 'rgba(0,0,0,0.04)' }},
                    border: {{ color: '#E7E5E4' }}
                  }}
                }},
                plugins: {{
                  legend: {{ display: false }},
                  tooltip: {{
                    backgroundColor: '#1C1917',
                    titleColor: '#FAF8F5',
                    bodyColor: '#F97316',
                    padding: 10,
                    callbacks: {{
                      label: function(ctx) {{
                        var v = ctx.parsed.y;
                        return v !== null ? ' ' + (v*100).toFixed(4)+'%' : ' N/A';
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
          <div class="empty-icon">&#9654;</div>
          <p>Waiting for the AI agent to write the first entry to <code>solution_log.json</code>.</p>
        </div>
"""

    cells_section = ""
    if has_cells:
        cells_section = """
        <div class="card" id="cells-card">
          <div class="card-label">Cell Breakdown</div>
          <div id="cells-content"></div>
        </div>
"""

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="10">
<title>MLE Bench Logger &mdash; {problem}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
:root {{
  --bg: #FAF8F5;
  --surface: #FFFFFF;
  --surface2: #F5F3F0;
  --surface3: #EDEBE7;
  --border: #E7E5E4;
  --text: #1C1917;
  --muted: #78716C;
  --muted2: #A8A29E;
  --accent: #F97316;
  --accent-light: rgba(249,115,22,0.10);
  --accent-hover: #EA6D0A;
  --changed: #D97706;
  --changed-bg: rgba(217,119,6,0.08);
  --green: #16A34A;
  --green-bg: rgba(22,163,74,0.08);
  --radius: 12px;
  --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', sans-serif;
  font-size: 14px;
  line-height: 1.6;
  min-height: 100vh;
}}
.site-header {{
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 32px;
  display: flex;
  align-items: center;
  height: 56px;
  gap: 10px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 1px 0 var(--border);
}}
.logo {{
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
}}
.logo-icon {{
  width: 32px;
  height: 32px;
  background: var(--accent);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: monospace;
  font-weight: 700;
  font-size: 13px;
  color: #fff;
  letter-spacing: -0.5px;
  flex-shrink: 0;
}}
.logo-name {{
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}}
.logo-name span {{ color: var(--accent); }}
.header-divider {{
  width: 1px;
  height: 20px;
  background: var(--border);
  margin: 0 4px;
}}
.header-title {{
  font-size: 14px;
  font-weight: 600;
  color: var(--muted);
}}
.header-right {{
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}}
.badge {{
  background: var(--accent);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 99px;
  letter-spacing: .4px;
  text-transform: uppercase;
}}
.badge-outline {{
  background: transparent;
  color: var(--accent);
  border: 1.5px solid var(--accent);
  font-size: 11px;
  font-weight: 600;
  padding: 2px 9px;
  border-radius: 99px;
  letter-spacing: .4px;
  text-transform: uppercase;
}}
.main-content {{
  max-width: 1140px;
  margin: 0 auto;
  padding: 28px 32px 48px;
}}
.problem-bar {{
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}}
.problem-name {{
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
}}
.card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: var(--shadow);
}}
.card-label {{
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--muted2);
  margin-bottom: 14px;
}}
.empty-state {{
  text-align: center;
  color: var(--muted);
  padding: 56px 20px;
}}
.empty-icon {{
  font-size: 32px;
  color: var(--accent);
  opacity: 0.4;
  margin-bottom: 12px;
}}
.empty-state code {{
  background: var(--surface2);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  color: var(--accent);
  font-family: monospace;
}}
#prompt-panel {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}}
@media (max-width: 720px) {{
  #prompt-panel {{ grid-template-columns: 1fr; }}
  .main-content {{ padding: 16px; }}
  .site-header {{ padding: 0 16px; }}
}}
.acc-display {{
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 14px;
}}
.acc-value {{
  font-size: 32px;
  font-weight: 800;
  color: var(--green);
  line-height: 1;
}}
.acc-label {{
  font-size: 12px;
  color: var(--muted);
  font-weight: 500;
}}
.model-chip {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--accent-light);
  color: var(--accent);
  font-size: 13px;
  font-weight: 700;
  padding: 5px 14px;
  border-radius: 99px;
  margin-bottom: 14px;
  border: 1px solid rgba(249,115,22,0.2);
}}
.hyperparam-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}}
.hyperparam-table td {{
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}}
.hyperparam-table td:first-child {{
  color: var(--muted);
  width: 48%;
  font-family: monospace;
  font-size: 12px;
}}
.prompt-selector {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}}
.prompt-btn {{
  background: var(--surface2);
  border: 1.5px solid var(--border);
  color: var(--muted);
  padding: 5px 16px;
  border-radius: 99px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  transition: all .15s ease;
}}
.prompt-btn:hover {{
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-light);
}}
.prompt-btn.active {{
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}}
.approach-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
}}
@media (max-width: 900px) {{
  .approach-grid {{ grid-template-columns: 1fr; }}
}}
.approach-section {{
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 18px;
}}
.approach-section-title {{
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .8px;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 7px;
}}
.approach-section-title .dot {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}}
.dot-orange {{ background: var(--accent); }}
.dot-blue {{ background: #3B82F6; }}
.dot-green {{ background: var(--green); }}
.approach-section-text {{
  color: var(--text);
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-wrap;
}}
.approach-model-name {{
  display: inline-flex;
  align-items: center;
  background: var(--accent-light);
  color: var(--accent);
  font-size: 13px;
  font-weight: 700;
  padding: 4px 12px;
  border-radius: 8px;
  margin-bottom: 10px;
  border: 1px solid rgba(249,115,22,0.2);
}}
.traj-text {{
  color: var(--muted);
  line-height: 1.7;
  font-size: 13px;
  white-space: pre-wrap;
}}
.user-prompt-box {{
  background: var(--surface2);
  border-left: 3px solid var(--accent);
  border-radius: 0 8px 8px 0;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--text);
  line-height: 1.6;
  font-style: italic;
}}
details {{
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;
}}
summary {{
  padding: 10px 16px;
  cursor: pointer;
  background: var(--surface2);
  font-size: 13px;
  font-weight: 600;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 8px;
  user-select: none;
  transition: background .15s;
}}
summary:hover {{ background: var(--surface3); }}
summary::-webkit-details-marker {{ display: none; }}
summary::before {{
  content: '▶';
  font-size: 9px;
  color: var(--accent);
  transition: transform .2s;
}}
details[open] summary::before {{ transform: rotate(90deg); }}
.cell-idx {{
  font-size: 11px;
  color: var(--muted);
  background: var(--border);
  padding: 2px 7px;
  border-radius: 4px;
  font-weight: 500;
}}
.lines-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}}
.lines-table th {{
  padding: 7px 10px;
  text-align: left;
  color: var(--muted2);
  border-bottom: 1px solid var(--border);
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .5px;
  background: var(--surface2);
}}
.lines-table td {{
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}}
.lines-table tr.changed-row td {{
  background: var(--changed-bg);
}}
.line-content {{
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  color: #44403C;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 11.5px;
}}
.line-num {{ color: var(--muted2); text-align: right; width: 36px; font-family: monospace; }}
.ai-sum {{ color: var(--text); font-size: 12px; }}
.changed-badge {{
  background: var(--changed);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  white-space: nowrap;
}}
.change-reason-row td {{
  background: rgba(217,119,6,0.05) !important;
  color: var(--changed);
  font-size: 12px;
  padding: 4px 10px 8px 10px;
  border-bottom: 1px solid var(--border) !important;
}}
.divider {{
  height: 1px;
  background: var(--border);
  margin: 20px 0;
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

function splitApproach(text) {{
  if (!text) return ['', '', ''];
  // Split by sentence boundaries
  var sents = text.match(/[^.!?]+[.!?]+ */g) || [text];
  var n = sents.length;
  if (n <= 1) return [text, '', ''];
  var t1 = Math.ceil(n / 3);
  var t2 = Math.ceil(2 * n / 3);
  return [
    sents.slice(0, t1).join('').trim(),
    sents.slice(t1, t2).join('').trim(),
    sents.slice(t2).join('').trim()
  ];
}}

function renderPanel(idx) {{
  var p = GYM_DATA.prompts[idx];
  if (!p) return;

  // accuracy
  var accEl = document.getElementById('acc-value');
  if (accEl) {{
    var acc = p.accuracy;
    accEl.textContent = acc !== null && acc !== undefined ? (acc * 100).toFixed(4) + '%' : 'N/A';
    accEl.style.color = acc !== null ? 'var(--green)' : 'var(--muted)';
  }}

  // approach summary → 3 sections
  var parts = splitApproach(p.approach_summary || '');
  var prepEl = document.getElementById('approach-preprocessing');
  var trainEl = document.getElementById('approach-training');
  if (prepEl) prepEl.textContent = parts[0] || (p.approach_summary || '—');
  if (trainEl) trainEl.textContent = parts[2] || parts[1] || '—';

  // model section
  var modelNameEl = document.getElementById('model-name');
  var modelHpEl = document.getElementById('model-hyperparams');
  var modelNoneEl = document.getElementById('model-none');
  var m = p.model;
  if (m && m.name) {{
    if (modelNameEl) {{ modelNameEl.textContent = m.name; modelNameEl.style.display = 'inline-flex'; }}
    if (modelNoneEl) modelNoneEl.style.display = 'none';
    if (modelHpEl) {{
      var hp = m.hyperparams || {{}};
      var rows = Object.entries(hp).map(function(kv) {{
        return '<tr><td>' + escHtml(kv[0]) + '</td><td>' + escHtml(String(kv[1])) + '</td></tr>';
      }}).join('');
      modelHpEl.innerHTML = rows
        ? '<table class="hyperparam-table"><tbody>' + rows + '</tbody></table>'
        : '<span style="color:var(--muted);font-size:12px">No hyperparameters recorded.</span>';
    }}
  }} else {{
    if (modelNameEl) modelNameEl.style.display = 'none';
    if (modelNoneEl) modelNoneEl.style.display = '';
    if (modelHpEl) modelHpEl.innerHTML = '';
    // fall back to middle part of approach for model section
    var midEl = document.getElementById('approach-model-text');
    if (midEl) midEl.textContent = parts[1] || '—';
  }}

  // trajectory
  var trajEl = document.getElementById('traj-text');
  if (trajEl) trajEl.textContent = p.trajectory_summary || '—';

  // user prompt
  var upEl = document.getElementById('user-prompt-text');
  if (upEl) upEl.textContent = p.user_prompt || '';

  renderCells(p);
}}

function renderCells(p) {{
  var container = document.getElementById('cells-content');
  if (!container) return;
  var cells = p.cells || [];
  if (!cells.length) {{
    container.innerHTML = '<p style="color:var(--muted);font-size:13px">No cell data for this prompt.</p>';
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
            '<td></td><td colspan="3">&#8627; ' + escHtml(ln.change_reason) + '</td>' +
          '</tr>';
      }}
      return mainRow + reasonRow;
    }}).join('');

    html +=
      '<details>' +
        '<summary>' +
          '<span class="cell-idx">cell&nbsp;' + cell.cell_index + '</span>' +
          escHtml(cell.cell_summary || 'Code cell') +
        '</summary>' +
        '<div style="overflow-x:auto;">' +
          '<table class="lines-table">' +
            '<thead><tr>' +
              '<th style="width:40px">#</th>' +
              '<th>Source</th><th>AI Summary</th>' +
              '<th style="width:76px">Status</th>' +
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
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

window.addEventListener('DOMContentLoaded', function() {{
  var prompts = GYM_DATA.prompts || [];
  var def = prompts.length - 1;
  for (var i = prompts.length - 1; i >= 0; i--) {{
    if (prompts[i].accuracy !== null && prompts[i].accuracy !== undefined) {{ def = i; break; }}
  }}
  if (def >= 0) selectPrompt(def);
}});
</script>

<header class="site-header">
  <a class="logo" href="#">
    <div class="logo-icon">&gt;_</div>
    <span class="logo-name">AI<span>Coding</span>Gym</span>
  </a>
  <div class="header-divider"></div>
  <span class="header-title">MLE Bench Logger</span>
  <div class="header-right">
    <span class="badge-outline">{ptype}</span>
    <span class="badge">Live</span>
  </div>
</header>

<div class="main-content">

<div class="problem-bar">
  <span class="problem-name">{problem}</span>
</div>

{prompt_selector_html}

{chart_section}

{"" if not has_prompts else """
<div id="prompt-panel">
  <div class="card">
    <div class="card-label">Accuracy</div>
    <div class="acc-display">
      <span class="acc-value" id="acc-value">—</span>
    </div>
    <div class="card-label" style="margin-top:6px">User Prompt</div>
    <div class="user-prompt-box" id="user-prompt-text"></div>
  </div>
  <div class="card">
    <div class="card-label">Trajectory Summary</div>
    <p id="traj-text" class="traj-text"></p>
  </div>
</div>

<div class="card">
  <div class="card-label">AI Approach Summary</div>
  <div class="approach-grid">
    <div class="approach-section">
      <div class="approach-section-title" style="color:var(--accent)">
        <span class="dot dot-orange"></span>Preprocessing
      </div>
      <p class="approach-section-text" id="approach-preprocessing"></p>
    </div>
    <div class="approach-section">
      <div class="approach-section-title" style="color:#3B82F6">
        <span class="dot dot-blue"></span>Model
      </div>
      <div class="approach-model-name" id="model-name" style="display:none"></div>
      <span id="model-none" style="color:var(--muted);font-size:12px;display:none">No model recorded.</span>
      <p class="approach-section-text" id="approach-model-text" style="color:var(--muted);font-size:13px"></p>
      <div id="model-hyperparams"></div>
    </div>
    <div class="approach-section">
      <div class="approach-section-title" style="color:var(--green)">
        <span class="dot dot-green"></span>Training Strategy
      </div>
      <p class="approach-section-text" id="approach-training"></p>
    </div>
  </div>
</div>
"""}

{cells_section}

</div><!-- /main-content -->
</body>
</html>"""

    return html


def _parse_notebook_cells(nb_path: Path) -> list:
    """Extract cell breakdown from solution.ipynb for dashboard display."""
    try:
        nb = json.loads(nb_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    result = []
    for idx, cell in enumerate(nb.get("cells", [])):
        cell_type = cell.get("cell_type", "code")
        source = cell.get("source", [])
        if isinstance(source, list):
            source = "".join(source)
        lines_split = source.split("\n")
        # Derive a summary from the first meaningful line
        summary = f"Cell {idx}"
        for ln in lines_split:
            s = ln.strip()
            if not s:
                continue
            if s.startswith("#"):
                summary = s.lstrip("#").strip()[:100]
            else:
                summary = s[:100]
            break
        line_entries = [
            {"line_index": li, "content": ln, "ai_summary": "", "changed": False, "change_reason": None}
            for li, ln in enumerate(lines_split)
            if ln.strip()
        ]
        result.append({
            "cell_index": idx,
            "cell_type": cell_type,
            "cell_summary": summary,
            "lines": line_entries,
        })
    return result


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

    # Auto-inject notebook cells for any prompt that has empty cells
    nb_path = log_path.parent / "solution.ipynb"
    if nb_path.exists():
        nb_cells = _parse_notebook_cells(nb_path)
        if nb_cells:
            for p in data.get("prompts", []):
                if not p.get("cells"):
                    p["cells"] = nb_cells

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
