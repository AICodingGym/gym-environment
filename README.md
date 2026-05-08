# AI Coding Gym — Gym Environment

The **gym environment** is the workspace where users solve [AI Coding Gym](https://aicodinggym.com) challenges with AI coding tools (e.g., Claude Code, Cursor, Gemini CLI). This repository is the template that seeds every new gym environment.

## What This Repo Does

The config files here are loaded automatically by AI coding agents when a user opens the environment. They serve three purposes:

1. **Instruct AI agents on the task workflow** — teach agents how to approach each challenge type (SWE-bench, MLE-bench, Code Review) and how to use the `aicodinggym` CLI to fetch, test, and submit solutions.

2. **Log user–agent interactions** — require agents to maintain a structured session log capturing every user prompt, the agent's approach, files touched, and outcomes. These logs are submitted alongside solutions for analysis. For MLE-bench, agents may also use `gym_log.json` (see `AGENTS.md`) for chat vs submission entries with per-model CV and leaderboard deltas; `aicodinggym mle submit` appends a submission record there when the competition directory exists.

3. **Steer agent behavior** — enforce constraints such as not searching the web for answers, not modifying test files, and staying focused on the problem at hand.

## Files

- **`AGENTS.md`** — Full exercise instructions, CLI reference, and logging format. Read by all AI agents.
- **`CLAUDE.md`** — Entry point for Claude Code (references `AGENTS.md`).
- **`GEMINI.md`** — Entry point for Gemini CLI (references `AGENTS.md`).
- **`supervisor.sh`** — Watcher + command wrapper. Auto-started in the background by the CLI after every fetch/download; appends compact activity cards to `dashboard.html` with collapsible per-file diffs.
- **`dashboard.html`** — Live dashboard (`<meta refresh>` every 5s) with a metric trend line, latest-metric banner, and activity feed. Populated by `supervisor.sh`.
- **`tools/notebook_metrics.py`** — Notebook executor/parser that prints `MAX_VALIDATION_ACCURACY=...` (extracted from `VAL_ACC: <float>` or `validation_accuracy: <float>` lines in notebook output).
- **`tools/summarize_approach.py`** — Parses `solution.ipynb` and emits the plain-English HTML fragment rendered in the dashboard's "Approach summary" panel (preprocessing / model / evaluation).

## Supervisor Usage

`aicodinggym swe fetch`, `aicodinggym mle download`, and `aicodinggym cr fetch`
all auto-start `./supervisor.sh --watch` in the background inside the new
problem folder. Its output goes to `<problem_dir>/.supervisor.log` and its PID
lives in `<problem_dir>/.supervisor.lock`. Open `dashboard.html` to see the
live feed.

If you obtained a challenge folder without using those commands (zip, manual copy), start the watcher once from that folder with `./supervisor.sh --watch`, or run `aicodinggym init-supervisors` from the parent workspace so every subdirectory gets supervisor assets and a background watcher.

You can also drive it by hand inside any challenge folder:

```bash
./supervisor.sh --help                     # full usage
./supervisor.sh --watch                    # manual start (if auto-start was skipped)
./supervisor.sh --cmd "python train.py"    # one-shot: snapshot, run, diff, re-extract metric
./supervisor.sh --submit                   # run the bound submit command and capture the result
./supervisor.sh --open                     # open dashboard.html in your browser
```

Optional alias:

```bash
alias gym-done='./supervisor.sh --submit'
```
