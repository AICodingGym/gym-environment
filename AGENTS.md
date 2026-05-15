# AI Coding Gym — Exercise Instructions

> This file is read by AI coding agents (Claude Code, Cursor, GitHub Copilot,
> Gemini CLI, Windsurf, and others) to understand the exercise context and
> logging requirements.

## About AI Coding Gym

[AI Coding Gym](https://aicodinggym.com) offers three types of coding challenges.
Check which type you are working on and follow the corresponding workflow below.

---

## Gym Watcher (Auto-starts on Every Problem)

Each fetched/downloaded challenge folder is seeded with:

- `gym_watcher.py` — Python watchdog that monitors `solution_log.json` and
  regenerates `dashboard.html` whenever the file changes
- `solution_log.json` — written by **you** (the AI agent) after each user message
- `dashboard.html` — generated automatically from `solution_log.json`

**Auto-start:** `aicodinggym swe fetch`, `aicodinggym mle download`, and
`aicodinggym cr fetch` each launch `gym_watcher.py` in the background, which
opens `dashboard.html` in the browser. The watcher logs to `.gym_watcher.log`.

To start it manually:
```bash
python gym_watcher.py <problem_dir>
```

---

## `solution_log.json` — Required for MLE-bench

After **every user message**, update `solution_log.json` in the problem folder.
Add one entry to the `prompts` array. Write atomically (write to
`solution_log.json.tmp` then rename) to avoid partial reads.

### Full Schema

```json
{
  "version": "1.0",
  "problem": "spaceship-titanic",
  "problem_type": "mle",
  "prompts": [
    {
      "prompt_index": 1,
      "user_prompt": "exact verbatim user message",
      "timestamp": "2026-05-14T10:23:00Z",
      "accuracy": 0.923,
      "model": {
        "name": "XGBoostClassifier",
        "hyperparams": {
          "n_estimators": 100,
          "max_depth": 6,
          "learning_rate": 0.1
        }
      },
      "approach_summary": "3-4 sentence overview of the technique used in this prompt",
      "trajectory_summary": "cumulative analysis of ALL prior prompts showing how accuracy improved",
      "cells": [
        {
          "cell_index": 0,
          "cell_type": "code",
          "cell_summary": "one-line summary of what this cell does",
          "lines": [
            {
              "line_index": 0,
              "content": "import pandas as pd",
              "ai_summary": "why this line exists",
              "changed": false,
              "change_reason": null
            },
            {
              "line_index": 5,
              "content": "X_train, X_val = train_test_split(X, test_size=0.2)",
              "ai_summary": "creates holdout set for accuracy estimation",
              "changed": true,
              "change_reason": "switched from 0.1 to 0.2 split to reduce variance in accuracy estimate, improving leaderboard generalization"
            }
          ]
        }
      ]
    }
  ]
}
```

### Field Rules

| Field | Rules |
|-------|-------|
| `accuracy` | **Must be a real measured float 0–1 after the notebook has run. Never `null` once predictions exist.** Evaluate on a training holdout or cross-validation score — do not skip this step. `null` only acceptable before first execution. For SWE/CR: `null` (no regression metric). |
| `model` | **Must be non-null for MLE-bench.** Name the strategy even when there is no ML model (e.g. `"MajorityLookup"`, `"RuleBasedNum2words"`). Record all key hyperparameters. |
| `cells` | **Required for MLE-bench where `solution.ipynb` exists — never an empty array.** One entry per code cell. `lines` must list every non-blank source line with `content` (exact source text) and `ai_summary` (why the line exists). Markdown cells may have `lines: []`. |
| `lines[].content` | Exact source text of the line. Copy verbatim from the notebook cell. |
| `lines[].ai_summary` | One short phrase explaining why this line exists. Required when `cells` is present. |
| `changed` | If `true`, `change_reason` must be non-null explaining **why** the line changed AND **how** it improves accuracy. |
| `trajectory_summary` | Covers ALL previous prompt entries — not just the prior one. Empty string OK on prompt 1. |
| `prompt_index` | 1-based, incrementing integer. |

### What the Dashboard Shows

The watcher regenerates `dashboard.html` on each write:
- **Accuracy line chart** — one point per prompt, clickable
- **Click a point** → shows model name + hyperparameters for that prompt
- **Approach summary** — 3-4 sentence overview of techniques
- **Trajectory summary** — cumulative analysis of progression
- **Cell breakdown** — expandable cells with per-line AI summaries;
  changed lines are highlighted with amber background and `change_reason`

### SWE-bench and Code Review

`solution_log.json` is optional for SWE-bench and Code Review (no notebook /
accuracy metric), but you may still write it to track your approach over multiple
prompts. Omit the `cells` and `model` fields; set `accuracy` to `null`.

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

For MLE-bench, your implementation must live in a **Jupyter notebook** in the
competition folder:

- Create and use: `<competition_id>/solution.ipynb`
- It must include the **full runnable pipeline** (load → train → predict → write CSV)
- You must **execute the notebook** so outputs exist
- You may create helper `.py` modules, but the notebook is the **source of truth**

### CLI Commands

```bash
aicodinggym mle download <competition_id>                  # Download dataset
aicodinggym mle submit <competition_id> -F predictions.csv # Submit predictions
aicodinggym mle submit <competition_id> -F pred.csv -m "XGBoost v2"
```

### Recommended Workflow

1. Download the dataset: `aicodinggym mle download <competition_id>`
2. Explore the data in `<competition_id>/data/`
3. Create `solution.ipynb` and build the full pipeline
4. Run the notebook so predictions CSV exists on disk
5. **Update `solution_log.json`** (see schema above) with this prompt's entry
6. Submit: `aicodinggym mle submit <competition_id> -F predictions.csv`

### Agent Execution Rules

- **Execute** training and inference yourself — do not only write scripts
- **Run the full notebook** so a predictions file exists on disk
- **Confirm** the file was written (path, row count) before reporting done
- **Update `solution_log.json`** in the same response after execution

---

## Challenge Type 3: Code Review

Review real pull requests from open-source projects. Identify bugs, security
issues, performance problems, and code quality concerns.

### CLI Commands

```bash
aicodinggym cr fetch <problem_id>                  # Clone the PR repo
aicodinggym cr submit <problem_id> -f review.md    # Submit review from file
aicodinggym cr submit <problem_id> -m "Review..."  # Submit review inline
```

### Recommended Workflow

1. Fetch the PR: `aicodinggym cr fetch <problem_id>`
2. Review `diff.patch` for bugs, security issues, and code quality problems
3. Write your review in `review.md`
4. Submit: `aicodinggym cr submit <problem_id> -f review.md`

---

## General Setup

If the CLI is not installed:

```bash
pip install aicodinggym
pip install watchdog>=4.0   # for gym_watcher.py
aicodinggym configure --user-id <USER_ID>
```

Get your user ID at [aicodinggym.com](https://aicodinggym.com).

## Exercise Rules

- Work only within this repository
- Do not access external services unless the problem requires it
- **Do not directly search on websites or online resources for solutions**
- Focus on the problem — avoid unrelated refactoring
- Use local tests to verify before submitting when available
- **Do not modify test files**
