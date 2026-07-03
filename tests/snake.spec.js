import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
});

// Continuously realigns the food directly in front of the snake's head so
// the very next tick eats it, avoiding any race with the game's own tick
// timer. Resolves with the score once it increases (or after a safety
// timeout, so a broken scoring path fails the assertion instead of hanging).
async function eatOneFood(page) {
  return page.evaluate(() => {
    return new Promise((resolve) => {
      const startScore = window.__game.score;
      const deadline = Date.now() + 3000;

      function align() {
        const g = window.__game;
        if (g.score > startScore || Date.now() > deadline) {
          resolve(g.score);
          return;
        }
        const head = g.snake[0];
        const dir = g.direction;
        window.__setFood(head.x + dir.x, head.y + dir.y);
        requestAnimationFrame(align);
      }

      align();
    });
  });
}

test("1. page loads and the game board is visible", async ({ page }) => {
  await expect(page.locator("#game-board")).toBeVisible();
});

test("2. initial score is 0", async ({ page }) => {
  await expect(page.locator("#score")).toContainText("0");
});

test("3. snake moves when an arrow key is pressed", async ({ page }) => {
  const before = await page.evaluate(() => window.__game.snake[0]);

  await page.keyboard.press("ArrowDown");
  await page.waitForTimeout(350);

  const after = await page.evaluate(() => window.__game.snake[0]);

  await expect(page.locator("#game-board")).toBeVisible();
  // Must have actually turned downward, not merely kept moving on its
  // default heading -- the snake auto-ticks every frame regardless of
  // input, so a weaker "position changed" check would pass even if the
  // ArrowDown key were never wired up correctly.
  expect(after.y).toBeGreaterThan(before.y);
  expect(after.x).toBe(before.x);
});

test("4. score increases after eating food", async ({ page }) => {
  const finalScore = await eatOneFood(page);

  expect(finalScore).toBeGreaterThan(0);
  await expect(page.locator("#score")).toContainText(String(finalScore));
});

test("5. game over appears after a collision", async ({ page }) => {
  await page.keyboard.press("ArrowRight");
  await expect(page.locator("#game-over")).toBeVisible({ timeout: 3000 });
});

test("6. restart button resets the game", async ({ page }) => {
  // Score must be nonzero before restart, otherwise a broken "reset score
  // on restart" path would go undetected (it would already read 0).
  const scoreBeforeRestart = await eatOneFood(page);
  expect(scoreBeforeRestart).toBeGreaterThan(0);

  await expect(page.locator("#game-over")).toBeVisible({ timeout: 5000 });

  await page.locator("#restart-button").click();

  await expect(page.locator("#game-over")).toBeHidden();
  await expect(page.locator("#score")).toContainText("0");
});
