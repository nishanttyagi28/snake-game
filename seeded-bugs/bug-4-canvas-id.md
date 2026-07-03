# Seeded Bug 4 — canvas id mismatch

**Target file:** `index.html`
**Location:** the board element.

**Before:**
```html
      <canvas id="game-board" width="400" height="400"></canvas>
```

**After (buggy):**
```html
      <canvas id="board" width="400" height="400"></canvas>
```

**Expected failing test:** `tests/snake.spec.js` test 1 ("page loads and the game board is visible") — `page.locator('#game-board')` matches nothing, so `toBeVisible()` fails.

**Cascading effect (expected, document it — don't "fix" it away):** `src/game.js`'s `init()` calls `document.getElementById("game-board")`, which now returns `null`; the immediately following `canvas.getContext("2d")` throws, so `init()` never finishes and `window.__game` / `window.__setFood` are never set. This will also fail tests 2–6 with a script error rather than a normal assertion failure. That cascade is realistic (a real typo like this would break the whole page) and is useful signal for the maintenance agent: the fix-request prompt should be able to identify the id mismatch from the stack trace/console error alone.
