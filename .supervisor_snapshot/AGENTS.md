# AI Coding Gym — Exercise Instructions

> This file is read by AI coding agents (Claude Code, Cursor, GitHub Copilot,
> Gemini CLI, Windsurf, and others) to understand the exercise context and
> logging requirements.

## About AI Coding Gym

[AI Coding Gym](https://aicodinggym.com) offers three types of coding challenges.
Check which type you are working on and follow the corresponding workflow below.

---

## Challenge Type 1: SWE-bench (Bug Fix)

Real bugs from open-source projects. Your goal is to identify and fix the bug
so that the project's test suite passes.

### Finding the Problem

- The problem is defined by a GitHub issue describing the bug, expected behavior,
  and reproduction steps
- Test files in `.github/workflows/` define what "passing" means
- Explore the codebase to understand the relevant code paths

### CLI Commands

```bash
aicodinggym swe fetch <problem_id>      # Clone the problem repo
aicodinggym swe test <problem_id>       # Run tests locally (needs Docker + act)
aicodinggym swe submit <problem_id>     # Submit your fix
aicodinggym swe submit <problem_id> -m "Fix null pointer in QuerySet filter"
aicodinggym swe reset <problem_id>      # Start over (destructive!)
```

### Recommended Workflow

1. Read the problem description and understand the expected behavior
2. Explore the codebase — find the relevant files and understand the bug
3. Write a fix
4. Run `aicodinggym swe test <problem_id>` to verify locally
5. If tests pass, run `aicodinggym swe submit <problem_id>`
6. If tests fail, iterate on the fix and test again

---

## Challenge Type 2: MLE-bench (Machine Learning Competition)

Kaggle-style ML competitions. Download a dataset, train a model, and submit
predictions as a CSV file.

### Notebook-first requirement (MLE-bench)

For MLE-bench, your implementation must live in a **Jupyter notebook** in the competition folder:

- Create and use: `<competition_id>/solution.ipynb`
- It must include the **full runnable pipeline** (extract/load → train/fit (if applicable) → predict → write CSV).
- You must **execute the notebook** so outputs exist (cell outputs / printed paths / basic sanity checks).
- You may also create helper `.py` modules, but the notebook is the **source of truth** and must be sufficient to reproduce the CSV.

### CLI Commands

```bash
aicodinggym mle download <competition_id>                    # Download dataset
aicodinggym mle log add <competition_id> --no-input -s "summary" --author ai   # Checkpoint (agent; all flags on CLI)
aicodinggym mle submit <competition_id> -F predictions.csv   # Submit predictions
aicodinggym mle submit <competition_id> -F pred.csv -m "XGBoost v2"
aicodinggym mle log show <competition_id>                    # View experiment timeline
```

### Recommended Workflow

1. Download the dataset: `aicodinggym mle download <competition_id>`
2. Explore the data in `<competition_id>/data/`
3. Train your model and generate predictions
4. Ensure your CSV matches the expected format (see `sample_submission.csv`)
5. Submit: `aicodinggym mle submit <competition_id> -F predictions.csv`
6. Check your score and iterate

### Agent execution (MLE-bench) — run the model and write results

You **must execute** training and inference yourself (terminal, notebook kernel you control, or your tool’s run action). **Do not** only write scripts or prose instructions and stop.

- **Write the code in `solution.ipynb`** (see Notebook-first requirement above) and **run it**.
- **Run** the full pipeline so a **predictions file exists on disk** (for example `submission.csv`, `predictions.csv`, or whatever the competition README/solution uses) under `<competition_id>/` unless the repo layout says otherwise.
- **Confirm** the file was written (path, row count vs `sample_submission.csv` when applicable) before you tell the user the work is done.
- **Immediately after a successful run** (same response): record metrics with a **non-interactive** checkpoint — `aicodinggym mle log add <competition_id> --no-input -s "…" --author ai` plus `--model` / `--val-metric` / `--val-score` when you have them, **or** append via Python: `ExperimentLog(Path("<competition_id>")).append(ExperimentLog(...).create_entry(...))`. **Do not** rely on the human to answer `mle log add` prompts.
- **Without waiting to be asked**, give the exact command: `aicodinggym mle submit <competition_id> -F <path-to-csv>`. State that **submit** records leaderboard (ground-truth) score, git/CSV provenance, and appends to `.mle_log.jsonl`, `gym_log.json`, and `.log/*.md` automatically.
- If the user asked not to submit to the platform, still **produce the CSV locally**, run checkpoint logging / `gym_log.json` / session log, and say so.
- Only skip execution when it is **impossible** in your environment (e.g. dataset not downloaded, missing required deps after a documented install attempt, no permission to run shell). Then say so plainly in your reply **and** in the session log **Outcome**.

---

## Challenge Type 3: Code Review

Review real pull requests from open-source projects. Identify bugs, security
issues, performance problems, and code quality concerns. Your review is
evaluated against human-written golden comments.

### CLI Commands

```bash
aicodinggym cr fetch <problem_id>                  # Clone the PR repo (base + head branches)
aicodinggym cr submit <problem_id> -f review.md    # Submit review from file
aicodinggym cr submit <problem_id> -m "Review..."  # Submit review inline
cat review.md | aicodinggym cr submit <problem_id> # Submit review via stdin
```

### Recommended Workflow

1. Fetch the PR: `aicodinggym cr fetch <problem_id>`
2. Compare the base and head branches to understand the changes
3. Review the diff for bugs, security issues, and code quality problems
4. Write your review with specific issues, file references, and severity levels
5. Submit: `aicodinggym cr submit <problem_id> -f review.md`
6. Aim for 100% recall — find all the issues the human reviewers found

---

## Session Log (REQUIRED)

You MUST create a session log file on your very first interaction and update it
continuously — do not batch-write at the end.

### Responsibility (agent vs human)

- **The AI agent** (you) is responsible for **automatically** appending session log entries. **Do not** ask the human to open `.log/`, copy prompts, or maintain this file by hand.
- On **every user message you answer**, append **one** new `## Entry N` (or merge a trivial follow-up into the same turn if you truly touched nothing — rare). Treat this as part of completing the reply, not optional paperwork.
- Entries added by the **`aicodinggym` CLI** (`mle submit`, `mle log add`) are separate and are labeled as not being chat turns; you still keep writing **chat** entries for conversational work.

### Log Location

Create the log at `<problem_id>/.log/<agent>-YYYYMMDD-HHMMSS.md` where the
timestamp is the session start time (no colons — filesystem-safe).

Examples: `django__django-10097/.log/claude-20260318-091500.md`,
`titanic/.log/cursor-20260318-143000.md`

To find the problem root:

- **SWE-bench:** run `git rev-parse --show-toplevel` inside the problem repo
  (the log is committed and pushed automatically on `swe submit`)
- **MLE-bench:** the folder containing `data/`
- **Code Review:** the folder containing `diff.patch`
- **If opened in a parent folder:** navigate into `<problem_id>/` first

### Log Header

Create the file on your very first interaction with this header:

```markdown
# Session Log

**Problem:** <problem slug, e.g. django__django-10097>
**Challenge type:** <SWE-bench | MLE-bench | Code Review>
**Started:** <ISO-8601 timestamp, e.g. 2026-03-13T14:00:00Z>
**Agent:** <your tool name, e.g. "Claude Code", "Cursor", "GitHub Copilot">

---
```

### Entry Format

Append a new entry for EVERY user message using this structure.

**All challenge types (minimum):**

```markdown
## Entry <N>

**Time:** <ISO-8601 timestamp>
**User prompt:** <Copy the user's message verbatim, or a faithful summary if >500 chars>
**Approach:** <1-3 sentences: what you plan to do>
**Files touched:** <comma-separated list of files you modified>
**Outcome:** <1 sentence: what happened>
```

**MLE-bench chat entries (add these fields in addition):**

- **One-sentence change description** (what actually changed in the codebase or notebook).
- **Models & validation:** each model you trained or evaluated, metric name, and score — or state that no evaluation was run.
- **Files created** and **Files modified** (explicit lists if helpful).
- **Files touched by human** (if any are known; otherwise write “none known”).
- **Execution:** commands or notebook cells you ran, or why execution was skipped.

**End of every MLE chat entry** — append this footer verbatim (replace `<competition_id>`):

```markdown
**Where to view summaries (structured metrics & history):**
- Tabular timeline (CV vs leaderboard, deltas): `<competition_id>/gym_log.json` — in Python: `from aicodinggym.gym_logger import print_summary, set_log_path` then `set_log_path("<competition_id>/gym_log.json"); print_summary()` (or open the JSON).
- Checkpoints, git hash, author: `<competition_id>/.mle_log.jsonl` — terminal: `aicodinggym mle log show <competition_id>` (or `aicodinggym mle log export <competition_id>`).
- This narrative thread: `<competition_id>/.log/` (this file).
```

**In your user-visible reply** (not only in `.log/*.md`), add a **one-line pointer**, e.g. “Structured metrics: see `gym_log.json` and `mle log show` under `<competition_id>/`.”

When the **CLI** appends an entry (`aicodinggym mle submit` or `mle log add`), **User prompt** is explicitly marked as not from a chat; those rows include **Entry kind** (`platform_submission` or `checkpoint`) and the same **Where to view summaries** footer. Optional **`CLI submit message (`-m`):`** appears only when you passed `-m` to `mle submit`. Set **`AICODINGGYM_AGENT`** in the environment if you want new log **filenames** to match your tool (default is “AI assistant”). The CLI **appends to the most recently modified** `*.md` in `.log/` when no file matches the current agent prefix. **Files touched** for MLE runs are limited to paths under the competition folder when the project lives inside a larger Git repository. If logging fails, the CLI prints **Warning: Session log append failed: …** instead of failing silently.

### Log Rules

- Create the file on your first interaction — do not wait
- **You** (the agent) append entries; the human does **not** owe manual logging
- First entry should include a brief summary of the problem being solved
- Never delete or alter previous entries — only append new ones
- Use incrementing entry numbers: Entry 1, Entry 2, Entry 3, ...
- If the user asks something unrelated, log it but mark as off-topic
- The log is submitted automatically with the solution — no user action needed for submission

## MLE-bench Experiment Logging (REQUIRED)

After EVERY response where you modify code files in an MLE-bench competition, **you** (the agent) MUST record a checkpoint — **not** the human via interactive prompts.

**Preferred (CLI, fully non-interactive):**

```bash
aicodinggym mle log add <competition_id> --no-input \
  -s "one-line description of what you changed" \
  --author ai \
  --model "ModelName" \
  --val-metric "metric_name" \
  --val-score 0.XXX
```

If you pass `-s` / `--summary`, the CLI does **not** prompt for other fields; omit optional flags when unknown.

**Alternative (Python API — same data as JSONL):**

```python
from pathlib import Path
from aicodinggym import ExperimentLog

comp = Path("<competition_id>")
log = ExperimentLog(comp)
entry = log.create_entry(
    summary="Trained ResNet baseline",
    author="ai",
    model="ResNet18",
    val_metric="accuracy",
    val_score=0.91,
    working_dir=comp,
    event_type="checkpoint",
)
log.append(entry)
```

### Rules

- **`--author ai`** (CLI) or `author="ai"` (Python) is **REQUIRED** for agent checkpoints.
- If you did not run evaluation, omit `--val-score` / `--val-metric`.
- If the change is not model-specific, omit `--model`.
- Do **NOT** log if your response only contained text/explanations (no code changes).
- Do **NOT** duplicate a checkpoint entry for the same change as `mle submit` — **submit** is auto-logged with ground truth, git revision, CSV hash, and API payload (sanitized).
- To review: `aicodinggym mle log show <competition_id>`

### What gets recorded automatically

- Git snapshot (full and short revision, branch, dirty file list cap) on each checkpoint and submit
- Which files changed and lines added/removed (from git diff) where applicable
- For **platform submission**: linked checkpoint id, CSV path/size/sha256, sanitized API result

### Relationship to session log

The session log (`.log/*.md`) captures prompts and narrative. The experiment log (`.mle_log.jsonl`) captures checkpoints and platform rows with provenance. Both run in parallel.

### Gym session JSON log (`gym_log.json`) — notebooks and leaderboard deltas

Structured log separating **local CV** from **leaderboard (ground truth)** and **submission deltas**. Path: `<competition_id>/gym_log.json`.

- **Notebooks:** `from aicodinggym.gym_logger import log_entry, print_summary, set_log_path` — use `entry_type="chat"` for CV rows; optional `provenance` dict.
- **CLI `mle submit`:** appends a **submission** row with `ground_truth_accuracy`, optional `provenance` (git short hash, CSV metadata), and `experiment_log_entry_id` linking to `.mle_log.jsonl`.

```python
from aicodinggym.gym_logger import log_entry, print_summary, set_log_path

log_entry(
    entry_type="chat",
    change_summary="Tuned max_depth 8→12 on ExtraTrees",
    models_used=["ExtraTreesClassifier"],
    per_model_accuracy={"ExtraTreesClassifier": cv_score},
)
print_summary()
```

**Three artifacts (MLE-bench):** `.log/*.md` (narrative), `.mle_log.jsonl` (checkpoints + submits + git/CSV/API), `gym_log.json` (CV vs leaderboard table). Do not invent leaderboard scores — only the API / `mle submit` sets ground truth.

---

## General Setup

If the CLI is not installed, run:

```bash
pip install aicodinggym
aicodinggym configure --user-id <USER_ID>
```

Get your user ID at [aicodinggym.com](https://aicodinggym.com).

## Exercise Rules

- Work only within this repository
- Do not access external services unless the problem requires it
- **Do not directly search on websites or online resources for solutions**
- Focus on the problem — avoid unrelated refactoring
- Use local tests to verify before submitting when available
- Commit your changes when the solution is ready
- **Do not modify test files**
