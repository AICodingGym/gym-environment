# AI Coding Gym

See [AGENTS.md](./AGENTS.md) for full exercise instructions, CLI reference,
and logging requirements.

## Key Requirements

- Create a session log at `<problem_id>/.log/<agent>-YYYYMMDD-HHMMSS.md` with an entry for every user interaction
- Use the appropriate CLI commands for your challenge type:
  - SWE-bench: `aicodinggym swe test/submit <id>`
  - MLE-bench: `aicodinggym mle download/submit <id>`
  - Code Review: `aicodinggym cr fetch/submit <id>`
- **Do not directly search on websites or online resources for solutions**
- **Do not modify test files**
- For MLE-bench: follow the experiment logging rules in [AGENTS.md](./AGENTS.md#mle-bench-experiment-logging-required)
- **For MLE-bench:** write `.agent_note.json` with `change_summary` and `why` before saving each significant change — see [AGENTS.md](./AGENTS.md#change-logging-required-for-mle-bench) for the protocol
