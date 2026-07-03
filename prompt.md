# Web-Based Snake Game Maintenance Agent

## 1. Objective
Build an autonomous harness agent that:
1. Creates/maintains a small web-based Snake Game repository.
2. Runs automated quality checks (unit tests, Playwright E2E tests, lint) against it.
3. Uses Claude (Anthropic API) to diagnose failures and propose minimal fixes.
4. Applies fixes, re-runs checks, and opens a pull request when a fix is verified — never merges automatically.
5. Files a GitHub issue for every failure it discovers, and comments on that issue if it cannot resolve it after a bounded number of attempts.

## 2. Definition of Done
- [ ] A new GitHub repo exists containing a working Snake Game (playable in a browser) and a Playwright test suite that passes against a clean checkout.
- [ ] `agent.py` can run against the repo, detect at least one of the 4 seeded bugs, open an issue, propose+apply a fix, re-run checks, and open a PR referencing the issue — without human intervention beyond reviewing/merging the PR.
- [ ] Secrets (API keys, tokens) never appear in commit history, issue bodies, PR bodies, or logs.
- [ ] The agent does not loop indefinitely on an unfixable failure.

## 3. Tech Stack & Environment
**Maintenance agent (Python):**
```
pip install anthropic pygithub gitpython python-dotenv pyyaml
```

**Target game (Node):**
```
npm install
npm install -D playwright vite eslint
npx playwright install --with-deps
```

**`.env` (agent side, never committed):**
```
ANTHROPIC_API_KEY=...
GITHUB_TOKEN=...   # scopes: repo (contents, issues, pull_requests)
```
Note: the fixer LLM is Claude — use the `anthropic` SDK, not `openai`.

## 4. Target Repository: Snake Game
### File layout
```
snake-game/
  index.html
  style.css
  src/
    game.js
  tests/
    snake.spec.js
  package.json
  playwright.config.js
  .eslintrc.json
```

### package.json scripts
```json
{
  "scripts": {
    "dev": "vite --host 0.0.0.0 --port 3000",
    "test": "echo \"no unit tests yet\" && exit 0",
    "e2e": "playwright test",
    "lint": "eslint ."
  }
}
```
`playwright.config.js` must set `webServer.command = "npm run dev"` and `baseURL = "http://localhost:3000"` so Playwright starts and owns the dev server itself instead of relying on a manually-started process (avoids port mismatches).

### Game functional spec
- Grid-based movement; snake advances one cell per tick.
- Arrow keys change direction; snake cannot reverse directly into itself.
- Eating food: increments `#score`, grows snake by one segment, spawns new food not on the snake.
- Colliding with a wall or itself ends the game and shows a `#game-over` element.
- `#restart-button` resets snake position, direction, and score to 0, and hides `#game-over`.
- `#score` always reflects current score, starting at `0`.
- The board element has a stable `id="game-board"` (must match tests exactly).
- Expose a test-only hook, e.g. `window.__setFood(x, y)`, so tests can force deterministic food placement (needed for the score-increase test — food is otherwise random and that test would be unwritable reliably).

## 5. Playwright Test Requirements
| # | Behavior | Key selector(s) |
|---|----------|------------------|
| 1 | Page loads, board visible | `#game-board` |
| 2 | Initial score is `0` | `#score` |
| 3 | Arrow key press changes snake position within 500ms | `#game-board` |
| 4 | Score increases after eating food (use `window.__setFood`) | `#score` |
| 5 | Game-over element appears after a forced collision | `#game-over` |
| 6 | Restart button resets score to 0 and hides game-over | `#restart-button`, `#score`, `#game-over` |

## 6. Maintenance Agent
### Folder structure
```
repo-maintenance-agent/
  agent.py
  config.yaml
  .env
  requirements.txt
  prompts/
    fix_prompt.txt
  work/        # gitignored scratch clone
  logs/        # gitignored run logs
```

### config.yaml
```yaml
repo_url: "https://github.com/<owner>/snake-game"
local_path: "./work/snake-game"
branch_prefix: "agent-maintenance"
max_fix_attempts: 3
checks:
  - "npm install"
  - "npm test"
  - "npm run lint"
  - "npx playwright test"
```

### Workflow
1. Clone or `git pull` the target repo into `local_path`.
2. Run each command in `checks`, capturing exit code, stdout, and stderr.
3. If all checks pass → log success, exit 0.
4. If any check fails:
   - Redact known secret patterns (tokens, keys) from captured logs before they're used anywhere.
   - Search open GitHub issues for one with a matching fingerprint (e.g. hash of the failing command + first error line); if found, reuse it instead of opening a duplicate.
   - Otherwise, open a new issue: failing command, condensed error summary, redacted logs, label `agent-maintenance`.
5. Fix-attempt loop (bounded by `max_fix_attempts`):
   - Gather relevant files: the file(s) named in the stack trace/error output, falling back to `src/game.js` plus the failing spec file if the trace doesn't localize.
   - Send `prompts/fix_prompt.txt`, filled in, to Claude.
   - Parse the response into `{file_path, explanation, replacement_code}`. Reject and retry if it references a file outside the repo or asks to touch more than one file.
   - Apply the change on branch `<branch_prefix>/fix-<short-desc>-<attempt-n>`.
   - Re-run the full `checks` list.
   - If all pass → go to step 6.
   - If not → revert the change, increment the attempt count, loop.
6. On success: commit, push the branch, open a PR that references the issue (`Closes #<n>`), and stop — never auto-merge. Comment on the issue linking the PR.
7. If `max_fix_attempts` is exhausted: comment on the issue summarizing every attempted fix and why it failed, add label `needs-human`, and stop.

## 7. LLM Fix-Request Prompt (`prompts/fix_prompt.txt`)
```
You are a repository maintenance agent working on a web-based Snake Game.

The following command failed:

COMMAND:
{cmd}

STDOUT:
{stdout}

STDERR:
{stderr}

Relevant files:
{relevant_files}

Rules:
- Suggest the smallest safe fix.
- Modify exactly one file.
- Preserve all existing passing behavior.
- Do not introduce new dependencies.
- Return strictly in this format:
  FILE: <path>
  EXPLANATION: <one paragraph>
  CODE:
  ```<language>
  <complete replacement file content>
  ```
```

## 8. Guardrails
- Never push directly to `main`/`master`; all changes go through a branch + PR.
- Never auto-merge a PR — merging is a human decision.
- Redact secrets from any text sent to GitHub (issues, PR bodies, comments) or written to `logs/`.
- Cap fix attempts at `max_fix_attempts`; no infinite retry loops.
- Before applying an LLM-proposed fix, validate via `git diff` that it touches only the one declared file.

## 9. Seeded Bugs for Testing the Agent
Introduce one at a time to validate detection + fix behavior:
1. Score never increments (`score = score;` instead of `score += 1;`) — fails test #4.
2. Restart doesn't reset score — fails test #6.
3. Arrow key handling uses wrong key names (`"Right"` instead of `"ArrowRight"`) — fails test #3.
4. Canvas id mismatch (`id="board"` instead of `id="game-board"`) — fails test #1.

## 10. What This Project Teaches
Browser automation, Playwright testing, GitHub issue/PR automation, LLM-based debugging, prompt design, error-log parsing, safe code editing, bounded agent retry loops, and human-approval gating. The real system is the harness around Claude — GitHub, Playwright, tests, logs, prompts, file editing, retry logic, and PR creation — not Claude alone.
