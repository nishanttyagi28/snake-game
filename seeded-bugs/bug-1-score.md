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
      this.score += 0;
      this.scoreEl.textContent = String(this.score);
      this.food = randomEmptyCell(this.snake);
    } else {
```

**Expected failing test:** `tests/snake.spec.js` test 4 ("score increases after eating food"). The snake still eats the food (it disappears/respawns and the snake grows), but `#score` stays at `0`, so `expect(finalScore).toBeGreaterThan(0)` fails once `eatOneFood()`'s 3s safety timeout resolves with the unchanged score.

Note: this must be a no-op that isn't a literal self-assignment (`this.score = this.score;`) -- ESLint's `no-self-assign` rule (part of `eslint:recommended`, enabled in `.eslintrc.json`) flags that form, which would make `npm run lint` fail before `npx playwright test` ever runs, masking the intended failure. `+= 0` is a genuine no-op that lint doesn't flag. (Found by actually running the seeded bug through the live agent -- see task.md X3.)

**Cascading effect (expected):** test 6 also fails, but only at its setup precondition (`expect(scoreBeforeRestart).toBeGreaterThan(0)`), since it eats food before testing restart. That's a side effect of sharing the `eatOneFood()` helper with test 4, not a second independent bug.
