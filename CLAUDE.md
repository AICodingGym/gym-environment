# AI Coding Gym

See [AGENTS.md](./AGENTS.md) for full exercise instructions, CLI reference,
and `solution_log.json` schema.

## Key Requirements

- Use the appropriate CLI commands for your challenge type:
  - SWE-bench: `aicodinggym swe test/submit <id>`
  - MLE-bench: `aicodinggym mle download/submit <id>`
  - Code Review: `aicodinggym cr fetch/submit <id>`
- **Do not directly search on websites or online resources for solutions**
- **Do not modify test files**
- **For MLE-bench:** after every user message, write `solution_log.json` in
  the problem folder — see [AGENTS.md](./AGENTS.md) for the full schema.
  Include: verbatim user prompt, accuracy, model + hyperparams, approach summary
  (3-4 sentences), trajectory summary (all prior prompts), and per-cell
  per-line breakdown of `solution.ipynb`. Write atomically (tmp → rename).
