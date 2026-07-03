<!-- double check the implementation for logical error, edge cases and architecture choices after the completion of each task and fix your issues. Run multiple agents at the same time for parallel task completion -->

# Task Breakdown — Snake Game Maintenance Agent

Source spec: `prompt.md`. This file splits that spec into independently-pickable tasks for parallel AI coding sessions. Each task lists the exact files it owns — no two open tasks should ever write to the same file, so sessions can run concurrently without merge conflicts.

## Shared Contracts (frozen — do not change without updating every task below)

All tasks that touch the game or the agent must conform to these interfaces exactly. Freezing them upfront is what lets tracks G and A run fully in parallel.

**DOM contract (game ↔ tests):**
- `#game-board` — the board/canvas element
- `#score` — text content is the current numeric score, starts at `0`
- `#restart-button` — click resets the game
- `#game-over` — hidden by default, visible after a loss
- `window.__setFood(x, y)` — test-only hook to force deterministic food placement

**Agent module interfaces (Python, one file per module):**
```python
# checks_runner.py
def run_cmd(cmd: str, cwd: str) -> dict          # {"cmd","code","stdout","stderr"}
def run_checks(repo_path: str, checks: list[str]) -> list[dict]
def has_failures(results: list[dict]) -> bool

# git_ops.py
def clone_or_pull(repo_url: str, local_path: str) -> None
def create_branch(repo_path: str, branch_name: str) -> None
def commit_all(repo_path: str, message: str) -> None
def push_branch(repo_path: str, branch_name: str) -> None
def revert_uncommitted(repo_path: str) -> None

# github_client.py
# DEVIATION (see A4): implemented as a class, not free functions, so the
# repo is a constructor param instead of hard-coded -- this was required by
# A4's own acceptance criterion. Methods match the original signatures
# below minus the implicit `self`.
class GitHubClient:
    def __init__(self, token: str, repo_full_name: str): ...
    def find_existing_issue(self, fingerprint: str) -> int | None: ...
    def create_issue(self, title: str, body: str, labels: list[str]) -> int: ...
    def comment_issue(self, issue_number: int, body: str) -> None: ...
    def add_label(self, issue_number: int, label: str) -> None: ...
    def create_pull_request(self, branch_name: str, title: str, body: str, base: str = "main") -> str: ...

# redact.py
def redact_secrets(text: str) -> str

# fixer.py
def build_fix_prompt(cmd: str, stdout: str, stderr: str, relevant_files: dict[str, str]) -> str
def request_fix(prompt: str) -> dict             # {"file_path","explanation","code"}
def validate_fix(repo_path: str, file_path: str) -> bool   # True iff git diff touches only file_path
```

If a task needs to deviate from a frozen interface, it must flag this in its own output instead of silently changing it, so `agent.py` (task A7) isn't broken by a surprise signature change.

---

## Track G — Snake Game Repository (`snake-game/`)

| ID | Task | Owns | Depends on |
|----|------|------|------------|
| G1 | Markup & styling | `index.html`, `style.css` | none |
| G2 | Game logic | `src/game.js` | none |
| G3 | Playwright test suite | `tests/snake.spec.js` | none |
| G4 | Build & lint config | `package.json`, `playwright.config.js`, `.eslintrc.json`, `.gitignore` | none |
| G5 | Seeded-bug patches | `seeded-bugs/*.md` (patch descriptions only, not applied to `src/game.js`) | none |

**G1 — Markup & styling**
Build `index.html` and `style.css` per prompt.md §4. Must include the exact IDs from the DOM contract above (`#game-board`, `#score`, `#restart-button`, `#game-over`). Score element must render `0` on initial load (even before `game.js` runs, so tests can check pre-JS state if needed — otherwise ensure `game.js` sets it on `DOMContentLoaded`). No game logic here, styling/layout only.
*Acceptance:* opening `index.html` shows a board, a score readout, a restart button, and a hidden game-over element, with no console errors from missing script tags (reference `src/game.js` as a module).

**G2 — Game logic**
Implement `src/game.js` per prompt.md §4 functional spec: grid movement, arrow-key input (no reversing into self), food-eating (score +1, grow, respawn food not on snake), wall/self collision → show `#game-over`, restart button resets state, `window.__setFood(x, y)` test hook. Pure JS, attach to the DOM IDs from the contract — do not invent different IDs.
*Acceptance:* game is playable manually in a browser after G1+G4 land; score increments on eating, game-over triggers on collision, restart works.

**G3 — Playwright test suite**
Write `tests/snake.spec.js` implementing the 6 tests in prompt.md §5, using the DOM contract IDs and `window.__setFood`. Write against the *contract*, not against G1/G2's actual code — do not wait for G1/G2 to merge to start.
*Acceptance:* once G1+G2+G4 are merged, `npx playwright test` passes all 6 tests with zero modification to this file.

**G4 — Build & lint config**
Create `package.json` (scripts: `dev`, `test`, `e2e`, `lint`, matching prompt.md §4), `playwright.config.js` (`webServer.command: "npm run dev"`, `baseURL: "http://localhost:3000"`), `.eslintrc.json` (reasonable defaults for vanilla JS), `.gitignore` (`node_modules/`, `playwright-report/`, `test-results/`).
*Acceptance:* `npm install && npm run dev` serves on port 3000; `npx playwright test` picks up `tests/snake.spec.js` automatically via `webServer`.

**G5 — Seeded-bug patches**
Write 4 standalone patch files under `seeded-bugs/` (`bug-1-score.md`, `bug-2-restart.md`, `bug-3-keys.md`, `bug-4-canvas-id.md`), each containing the exact one-line diff from prompt.md §9 and which test it should break. Do not touch `src/game.js` or `index.html` directly — these are applied manually/by the agent later during Track X validation, one at a time, so they never conflict with G1/G2 development.
*Acceptance:* each patch file states the target file, the exact before/after line, and the expected failing test number from §5.

---

## Track A — Maintenance Agent (`repo-maintenance-agent/`)

| ID | Task | Owns | Depends on |
|----|------|------|------------|
| A1 | Scaffolding & config | `config.yaml`, `.env.example`, `requirements.txt`, `.gitignore`, `logs/.gitkeep`, `work/.gitkeep` | none |
| A2 | Check runner | `checks_runner.py` (+ its own tests) | none (interface frozen above) |
| A3 | Git operations | `git_ops.py` (+ its own tests) | none |
| A4 | GitHub client | `github_client.py` (+ its own tests) | none |
| A5 | Secret redaction | `redact.py` (+ its own tests) | none |
| A6 | Fixer (Claude integration) | `fixer.py`, `prompts/fix_prompt.txt` (+ its own tests) | none |
| A7 | Orchestrator | `agent.py` | soft: A1–A6 interfaces (frozen above); hard: needs A1–A6 *merged* to actually run end-to-end |

**A1 — Scaffolding & config**
Create `config.yaml` matching prompt.md §6 schema exactly (`repo_url`, `local_path`, `branch_prefix`, `max_fix_attempts`, `checks`), `.env.example` listing `ANTHROPIC_API_KEY` and `GITHUB_TOKEN` (no real values), `requirements.txt` pinning `anthropic`, `pygithub`, `gitpython`, `python-dotenv`, `pyyaml`, and `.gitignore` excluding `.env`, `work/`, `logs/`.
*Acceptance:* `pip install -r requirements.txt` succeeds; `config.yaml` parses with `yaml.safe_load`.

**A2 — Check runner**
Implement `checks_runner.py` exactly per the frozen interface. `run_cmd` uses `subprocess.run(shell=True, text=True, capture_output=True)`. Include unit tests using a trivial command (e.g. `python -c "print(1)"`) that don't depend on any other track.
*Acceptance:* unit tests pass standalone with no network/repo access.

**A3 — Git operations**
Implement `git_ops.py` using `gitpython`, per the frozen interface. `clone_or_pull` clones if `local_path` doesn't exist, else fetches+pulls. `revert_uncommitted` discards working-tree changes (but never touches other branches). Test against a scratch local git repo created in a temp dir — do not depend on the real `snake-game` repo existing.
*Acceptance:* unit tests pass against a locally-created throwaway git repo.

**A4 — GitHub client**
Implement `github_client.py` using `pygithub`, per the frozen interface. `find_existing_issue(fingerprint)` searches open issues labeled `agent-maintenance` for one whose body contains the fingerprint string. Mock the GitHub API in tests (no live network calls in the test suite).
*Acceptance:* unit tests pass using a mocked `Github` client; no hard-coded repo name inside the module (must accept repo as a constructor/param).

**A5 — Secret redaction**
Implement `redact.py`: `redact_secrets(text)` scrubs common token patterns (`ghp_...`, `sk-ant-...`, generic `KEY=`/`TOKEN=` assignments, bearer tokens) and replaces them with `[REDACTED]`. Include unit tests with sample strings containing fake secrets.
*Acceptance:* unit tests confirm known patterns are redacted and normal log text is left untouched.

**A6 — Fixer (Claude integration)**
Write `prompts/fix_prompt.txt` verbatim from prompt.md §7. Implement `fixer.py`: `build_fix_prompt` fills the template, `request_fix` calls the Anthropic API and returns the parsed `{file_path, explanation, code}` dict (raise `ValueError` on a malformed response — missing `FILE:`/`CODE:` markers, more than one file, etc.), `validate_fix` shells out to `git diff --name-only` and checks the result is exactly `[file_path]`. Mock the Anthropic API call in tests.
*Acceptance:* unit tests cover a well-formed response (parses correctly) and at least two malformed ones (raises `ValueError`).

**A7 — Orchestrator**
Implement `agent.py`, wiring A1–A6 per the Workflow in prompt.md §6: load config → `clone_or_pull` → `run_checks` → if failures, redact logs, dedup-or-create issue, run the bounded fix-attempt loop (branch → apply fix → re-run checks → revert-on-failure), then on success push+PR+comment, or on exhaustion comment+label `needs-human`. Can be authored immediately against the frozen interfaces (import the modules and code to their signatures) — only *running* it end-to-end requires A1–A6 to be merged.
*Acceptance:* a dry run against a repo with all checks passing exits 0 without opening an issue; code review confirms every step of the §6 Workflow is represented.

---

## Track X — Integration (sequenced; not parallel with each other)

| ID | Task | Owns | Depends on |
|----|------|------|------------|
| X1 | Create GitHub repo & push scaffold | (GitHub-side repo creation, no local file conflicts) | G1–G4 content ready to push |
| X2 | End-to-end dry run (clean repo) | none (verification only, fixes go back into owning task's files) | G1–G4, A1–A7 |
| X3 | Seeded-bug validation (4 runs) | none (verification only) | X2, G5 |
| X4 | Top-level README | `README.md` | can start anytime; finalize after X2/X3 |

**X1 — Create GitHub repo & push scaffold**
Create the new GitHub repository referenced in `config.yaml`'s `repo_url`, push the initial `snake-game/` scaffold (whatever of G1–G4 is ready) to `main`. One-time setup; requires repo-creation credentials/permissions.
*Acceptance:* repo exists, is cloneable, contains the current game scaffold.

**X2 — End-to-end dry run**
With G1–G4 and A1–A7 merged, and the game bug-free, run `agent.py` against the real repo. Confirm: all checks pass, agent logs success, exits 0, and opens no issue. If something doesn't wire together (an interface mismatch slipped through), fix it in the *owning* task's file, not by improvising in `agent.py`.
*Acceptance:* clean run, exit code 0, no GitHub side effects.

**X3 — Seeded-bug validation**
Apply each `seeded-bugs/*.md` patch from G5 one at a time (on a scratch branch, reverted between runs), run `agent.py`, and confirm for each: the correct test fails, an issue is opened with redacted logs, a fix is proposed/applied, checks re-run, and (if fixed) a PR opens referencing the issue — or, if not fixed within `max_fix_attempts`, the issue gets the `needs-human` label and a summary comment.
*Acceptance:* all 4 seeded bugs produce the expected issue/PR (or needs-human) outcome per prompt.md §9.

**X4 — Top-level README**
Write `README.md` at the project root: what this project is, how to run the game locally, how to run the agent, and a link back to `prompt.md` for the full spec. Touches only `README.md`, so it can be drafted early and refined once X2/X3 confirm actual behavior.
*Acceptance:* a new contributor can follow it to run both the game and the agent without reading `prompt.md` first.

---

## Parallelization Summary

- **Start immediately, fully parallel, zero shared files:** G1, G2, G3, G4, G5, A1, A2, A3, A4, A5, A6, A7 (author against frozen interfaces), X1, X4 (draft).
- **Convergence point 1 (X2):** requires G1–G4 and A1–A7 merged. Run after the above land.
- **Convergence point 2 (X3):** requires X2 to have passed, plus G5. Run last.
- If any task discovers the frozen contract (DOM IDs or module interfaces) needs to change, that change must be posted back into this file's "Shared Contracts" section before other in-flight tasks are affected — treat the contract as the one piece of shared state everyone reads.
