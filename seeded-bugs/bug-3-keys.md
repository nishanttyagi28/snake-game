# Seeded Bug 3 — wrong key handling

**Target file:** `src/game.js`
**Location:** the `DIRECTIONS` key-mapping table.

**Before:**
```js
const DIRECTIONS = {
  ArrowUp: { x: 0, y: -1 },
  ArrowDown: { x: 0, y: 1 },
  ArrowLeft: { x: -1, y: 0 },
  ArrowRight: { x: 1, y: 0 },
};
```

**After (buggy):**
```js
const DIRECTIONS = {
  ArrowUp: { x: 0, y: -1 },
  Down: { x: 0, y: 1 },
  ArrowLeft: { x: -1, y: 0 },
  ArrowRight: { x: 1, y: 0 },
};
```

**Expected failing test:** `tests/snake.spec.js` test 3 ("snake moves when an arrow key is pressed"). `event.key` for the down arrow is always `"ArrowDown"` in a real browser, so `DIRECTIONS[event.key]` is now `undefined` and `setDirection()` silently no-ops. The snake keeps moving on its default rightward heading instead of turning down, so `expect(after.y).toBeGreaterThan(before.y)` fails (and `expect(after.x).toBe(before.x)` would also fail, since x keeps changing instead).

Note: `INITIAL_DIRECTION` is a separate constant from this table specifically so this bug stays localized to input handling and doesn't also break the snake's starting direction (see the comment above `DIRECTIONS` in `src/game.js`).
