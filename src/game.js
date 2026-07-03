const GRID_SIZE = 20;
const CELL = 20;
const TICK_MS = 100;

// Kept separate from the direction vectors below so a bug in this key
// mapping can't also corrupt the snake's default/initial direction.
const DIRECTIONS = {
  ArrowUp: { x: 0, y: -1 },
  Down: { x: 0, y: 1 },
  ArrowLeft: { x: -1, y: 0 },
  ArrowRight: { x: 1, y: 0 },
};

const INITIAL_DIRECTION = { x: 1, y: 0 }; // right

function isOpposite(a, b) {
  return a.x === -b.x && a.y === -b.y;
}

function randomEmptyCell(snake) {
  const occupied = new Set(snake.map((s) => `${s.x},${s.y}`));
  let cell;
  do {
    cell = {
      x: Math.floor(Math.random() * GRID_SIZE),
      y: Math.floor(Math.random() * GRID_SIZE),
    };
  } while (occupied.has(`${cell.x},${cell.y}`));
  return cell;
}

class SnakeGame {
  constructor(canvas, scoreEl, gameOverEl) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.scoreEl = scoreEl;
    this.gameOverEl = gameOverEl;
    this.intervalId = null;
    this.score = 0; // explicit initial value so a broken reset() (see seeded-bugs/bug-2-restart.md) only affects actual restarts, not first load
    this.reset();
  }

  reset() {
    this.snake = [
      { x: 10, y: 10 },
      { x: 9, y: 10 },
      { x: 8, y: 10 },
    ];
    this.direction = INITIAL_DIRECTION;
    this.pendingDirection = INITIAL_DIRECTION;
    this.score = 0;
    this.gameOver = false;
    this.food = randomEmptyCell(this.snake);

    this.scoreEl.textContent = String(this.score);
    this.gameOverEl.hidden = true;

    if (this.intervalId !== null) {
      clearInterval(this.intervalId);
    }
    this.intervalId = setInterval(() => this.tick(), TICK_MS);

    this.render();
  }

  setDirection(key) {
    const next = DIRECTIONS[key];
    if (!next) return;
    if (isOpposite(next, this.direction)) return;
    this.pendingDirection = next;
  }

  setFood(x, y) {
    this.food = { x, y };
    this.render();
  }

  tick() {
    if (this.gameOver) return;

    this.direction = this.pendingDirection;
    const head = this.snake[0];
    const newHead = { x: head.x + this.direction.x, y: head.y + this.direction.y };

    const hitWall =
      newHead.x < 0 || newHead.x >= GRID_SIZE || newHead.y < 0 || newHead.y >= GRID_SIZE;
    const ateFood = !hitWall && newHead.x === this.food.x && newHead.y === this.food.y;

    // The tail cell is vacated this tick unless the snake is growing, so it
    // must be excluded from the self-collision check (otherwise moving into
    // the cell the tail is leaving is wrongly flagged as a collision).
    const bodyToCheck = ateFood ? this.snake : this.snake.slice(0, -1);
    const hitSelf = bodyToCheck.some((seg) => seg.x === newHead.x && seg.y === newHead.y);

    if (hitWall || hitSelf) {
      this.endGame();
      return;
    }

    this.snake.unshift(newHead);

    if (ateFood) {
      this.score += 1;
      this.scoreEl.textContent = String(this.score);
      this.food = randomEmptyCell(this.snake);
    } else {
      this.snake.pop();
    }

    this.render();
  }

  endGame() {
    this.gameOver = true;
    if (this.intervalId !== null) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    this.gameOverEl.hidden = false;
  }

  render() {
    const { ctx } = this;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    ctx.fillStyle = "#4ade80";
    for (const seg of this.snake) {
      ctx.fillRect(seg.x * CELL, seg.y * CELL, CELL - 1, CELL - 1);
    }

    ctx.fillStyle = "#f87171";
    ctx.fillRect(this.food.x * CELL, this.food.y * CELL, CELL - 1, CELL - 1);
  }
}

function init() {
  const canvas = document.getElementById("game-board");
  const scoreEl = document.getElementById("score");
  const gameOverEl = document.getElementById("game-over");
  const restartButton = document.getElementById("restart-button");

  const game = new SnakeGame(canvas, scoreEl, gameOverEl);

  document.addEventListener("keydown", (event) => {
    if (Object.prototype.hasOwnProperty.call(DIRECTIONS, event.key)) {
      event.preventDefault();
      game.setDirection(event.key);
    }
  });

  restartButton.addEventListener("click", () => game.reset());

  // Test-only hook: force deterministic food placement (grid coordinates, not pixels).
  window.__setFood = (x, y) => game.setFood(x, y);
  window.__game = game;
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
