# Snake Game + Maintenance Agent

A small web-based Snake Game, plus an autonomous maintenance agent that runs its checks, opens GitHub issues for failures, asks Claude for a minimal fix, and opens a PR if the fix is verified.

Full spec: [`prompt.md`](./prompt.md). Task breakdown used to build this: [`task.md`](./task.md).

## Running the game

Requires Node.js.

```
npm install
npm run dev        # serves the game at http://localhost:3000
```

Run the Playwright test suite (starts the dev server itself):

```
npx playwright test
```

Lint:

```
npm run lint
```

### Seeded bugs

`seeded-bugs/*.md` documents 4 small, deliberate bugs (see [`prompt.md` §9](./prompt.md)) you can apply one at a time to `src/game.js` / `index.html` to exercise the maintenance agent's detect → fix → PR loop. Each file states the exact before/after diff and which Playwright test it should break.

## Running the maintenance agent

```
cd repo-maintenance-agent
python -m venv .venv
.venv/Scripts/activate        # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env          # fill in ANTHROPIC_API_KEY and GITHUB_TOKEN
```

Edit `config.yaml` — in particular set `repo_url` to a real GitHub repo (it defaults to a `<owner>` placeholder).

```
python agent.py
```

On a clean repo it clones/pulls, runs the checks in `config.yaml`, and exits `0` with no GitHub side effects. On a failing repo it opens (or reuses) a GitHub issue, attempts up to `max_fix_attempts` fixes via Claude, and either opens a PR referencing the issue or labels it `needs-human` if it can't resolve it. It never pushes to `main` or auto-merges — every fix lands as a PR for a human to review.

Run the agent's own unit tests:

```
python -m pytest tests/
```

## Project status

- Game (`index.html`, `style.css`, `src/game.js`, `tests/snake.spec.js`) and the maintenance agent (`repo-maintenance-agent/`) are both implemented and unit-tested.
- The agent's Python test suite (49 tests) passes, including a real (non-mocked) dry run of the clone → check → exit-0 path against a scratch git repo.
- The game's own Playwright suite has **not** been executed in this environment (no Node.js available here) — run `npx playwright test` yourself to confirm before relying on it.
- Creating the real GitHub repo and running the agent against real seeded-bug failures (opening real issues/PRs) hasn't been done yet — see `task.md`'s X1/X3.
