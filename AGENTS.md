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

### CLI Commands

```bash
aicodinggym mle download <competition_id>                    # Download dataset
aicodinggym mle submit <competition_id> -F predictions.csv   # Submit predictions
aicodinggym mle submit <competition_id> -F pred.csv -m "XGBoost v2"
```

### Recommended Workflow

1. Download the dataset: `aicodinggym mle download <competition_id>`
2. Explore the data in `<competition_id>/data/`
3. Train your model and generate predictions
4. Ensure your CSV matches the expected format (see `sample_submission.csv`)
5. Submit: `aicodinggym mle submit <competition_id> -F predictions.csv`
6. Check your score and iterate

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

Append a new entry for EVERY user message using this structure:

```markdown
## Entry <N>

**Time:** <ISO-8601 timestamp>
**User prompt:** <Copy the user's message verbatim, or a faithful summary if >500 chars>
**Approach:** <1-3 sentences: what you plan to do>
**Files touched:** <comma-separated list of files you modified>
**Outcome:** <1 sentence: what happened>
```

### Log Rules

- Create the file on your first interaction — do not wait
- First entry should include a brief summary of the problem being solved
- Never delete or alter previous entries — only append new ones
- Use incrementing entry numbers: Entry 1, Entry 2, Entry 3, ...
- If the user asks something unrelated, log it but mark as off-topic
- The log is submitted automatically with the solution — no user action needed

## MLE-bench Experiment Logging (REQUIRED)

After EVERY response where you modify code files in an MLE-bench competition, you MUST log a checkpoint:

```bash
aicodinggym mle log add <competition_id> \
  --summary "one-line description of what you changed" \
  --model "ModelName" \
  --val-metric "metric_name" \
  --val-score 0.XXX \
  --author ai
```

### Rules

- The `--author ai` flag is **REQUIRED** for correct attribution
- If you did not run evaluation, omit `--val-score` and `--val-metric`
- If the change is not model-specific, omit `--model`
- Do **NOT** log if your response only contained text/explanations (no code changes)
- Do **NOT** log after `mle submit` — that is auto-logged with the ground truth score
- To review the timeline: `aicodinggym mle log show <competition_id>`

### What gets recorded automatically

- Which files changed and lines added/removed (from git diff)
- Current git hash
- Timestamp

### Relationship to session log

The session log (Entry 1, 2, 3… in `.log/`) captures every prompt and response.
The experiment log (`.mle_log.jsonl`) captures model checkpoints and scores.
Both run in parallel — keep writing session log entries as before.

### Gym session JSON log (`gym_log.json`) — notebooks and leaderboard deltas

Optional structured log for MLE work that separates **local CV** from **leaderboard (ground truth)** scores and tracks **submission-to-submission** deltas. Lives at `<competition_id>/gym_log.json` (same folder as `data/`).

**When to use it**

- **Jupyter / Kaggle:** import the logger and call `log_entry` after CV tuning (`entry_type="chat"`) and after you know the leaderboard score (`entry_type="submission"`). Set the file explicitly if needed, e.g. `set_log_path("<competition>/gym_log.json")` or env `GYM_LOG_PATH`.
- **CLI:** running `aicodinggym mle submit …` **appends a submission row** to `gym_log.json` with the API score as `ground_truth_accuracy`. If the latest `.mle_log.jsonl` entry has a model name and validation score, those are copied into `models_used` / `per_model_accuracy` for that row. `delta_from_last_submission` is computed automatically vs the previous row that had a ground-truth score.

**Python API** (package or copy `gym_logger.py` next to the notebook):

```python
from aicodinggym.gym_logger import log_entry, print_summary, set_log_path

log_entry(
    entry_type="chat",
    change_summary="Tuned max_depth 8→12 on ExtraTrees",
    models_used=["ExtraTreesClassifier"],
    per_model_accuracy={"ExtraTreesClassifier": cv_score},
)
log_entry(
    entry_type="submission",
    change_summary="Submitted stacking v2",
    models_used=["ExtraTrees", "HistGradient"],
    per_model_accuracy={"ExtraTrees": 0.812, "HistGradient": 0.804},
    ensemble_accuracy=0.821,
    ground_truth_accuracy=leaderboard_score,
)
print_summary()
```

**Relationship to `.mle_log.jsonl`**

- `.mle_log.jsonl` — CLI-oriented lines with git diff, single `model` / val / submit fields; use `aicodinggym mle log add` after code changes.
- `gym_log.json` — narrative `change_summary`, `chat` vs `submission`, **per-model CV dict**, optional `ensemble_accuracy`, and explicit delta between leaderboard scores.

Use both if you want git-attributed checkpoints plus a notebook-friendly accuracy timeline.

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
