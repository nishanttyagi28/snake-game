# Seeded Bug 2 — restart does not reset score

**Target file:** `src/game.js`
**Location:** inside `reset()`.

**Before:**
```js
    this.direction = INITIAL_DIRECTION;
    this.pendingDirection = INITIAL_DIRECTION;
    this.score = 0;
    this.gameOver = false;
```

**After (buggy):**
```js
    this.direction = INITIAL_DIRECTION;
    this.pendingDirection = INITIAL_DIRECTION;
    // this.score = 0;
    this.gameOver = false;
```

**Expected failing test:** `tests/snake.spec.js` test 6 ("restart button resets the game"). The test deliberately eats one food item (via `eatOneFood()`) before forcing a collision, so the score is nonzero going into restart. After clicking `#restart-button`, `#score` still shows the pre-restart value instead of `0`, failing `expect(page.locator("#score")).toContainText("0")`.

Note: `#score`'s DOM text is only refreshed elsewhere when score changes during play (`tick()`'s `ateFood` branch) or on `reset()` itself, so this bug is not masked by a stray re-render.
