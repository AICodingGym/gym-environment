# AI Coding Gym — Exercise Instructions

> This file is read by AI coding agents (Claude Code, Cursor, GitHub Copilot,
> Gemini CLI, Windsurf, and others) to understand the exercise context.

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

## General Setup

If the CLI is not installed, run:

```bash
pip install aicodinggym-cli
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
