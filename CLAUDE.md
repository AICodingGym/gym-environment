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
- **Before any `submit`:** write `.gym_attribution.json` in the problem folder
  with your `tool`, `ai_model`, and (if known) `tool_version` so the leaderboard
  credits the right tool/model. See [AGENTS.md](./AGENTS.md) for the schema.
- **For MLE-bench:** after every user message, write `solution_log.json` in
  the problem folder — see [AGENTS.md](./AGENTS.md) for the full schema.
  Write atomically (tmp → rename).

## solution_log.json — Hard Rules (MLE-bench)

Violating these makes the dashboard useless:

1. **`accuracy` must be a real measured float — never `null`.** Run the notebook,
   evaluate on a holdout or training sample, compute the score, and write it.
   `null` is only acceptable before the notebook has ever been executed.

2. **`cells` must match every code cell in `solution.ipynb`.** For each cell include:
   - `cell_summary`: one human-readable sentence describing what the cell does
   - `lines`: every non-blank source line with `line_index`, `content` (exact source),
     and `ai_summary` (why the line exists). Do not leave `lines` as `[]`.

3. **`model` must be non-null.** Even for lookup/rule-based approaches, name the
   strategy (e.g. `"MajorityLookup"`) and record key hyperparameters.

4. **`approach_summary` must be 3–4 sentences** covering: what data was used,
   what technique was applied, what the accuracy result was, and what changed
   vs the previous prompt (if any).

5. **`trajectory_summary`** must cover ALL prior prompts cumulatively.
   Empty string is only acceptable on prompt 1.
