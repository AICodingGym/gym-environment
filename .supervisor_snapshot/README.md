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
