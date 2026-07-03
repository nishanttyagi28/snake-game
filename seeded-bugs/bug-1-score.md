# Seeded Bug 1 — score does not increase

**Target file:** `src/game.js`
**Location:** inside `tick()`, in the `ateFood` branch.

**Before:**
```js
    if (ateFood) {
      this.score += 1;
      this.scoreEl.textContent = String(this.score);
      this.food = randomEmptyCell(this.snake);
    } else {
```

**After (buggy):**
```js
    if (ateFood) {
      this.score = this.score;
      this.scoreEl.textContent = String(this.score);
      this.food = randomEmptyCell(this.snake);
    } else {
```

**Expected failing test:** `tests/snake.spec.js` test 4 ("score increases after eating food"). The snake still eats the food (it disappears/respawns and the snake grows), but `#score` stays at `0`, so `expect(finalScore).toBeGreaterThan(0)` fails once `eatOneFood()`'s 3s safety timeout resolves with the unchanged score.
