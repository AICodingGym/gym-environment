# AI Coding Gym — Gym Environment

The **gym environment** is the workspace where users solve [AI Coding Gym](https://aicodinggym.com) challenges with AI coding tools (e.g., Claude Code, Cursor, Gemini CLI). This repository is the template that seeds every new gym environment.

## What This Repo Does

The config files here are loaded automatically by AI coding agents when a user opens the environment. They serve two purposes:

1. **Instruct AI agents on the task workflow** — teach agents how to approach each challenge type (SWE-bench, MLE-bench, Code Review) and how to use the `aicodinggym` CLI to fetch, test, and submit solutions.

2. **Steer agent behavior** — enforce constraints such as not searching the web for answers, not modifying test files, and staying focused on the problem at hand.

## Files

- **`AGENTS.md`** — Full exercise instructions and CLI reference. Read by all AI agents.
- **`CLAUDE.md`** — Entry point for Claude Code (references `AGENTS.md`).
- **`GEMINI.md`** — Entry point for Gemini CLI (references `AGENTS.md`).
