// Playwright's API server: bring canyon_e2e to a known state, then serve it. Seeding happens here, before
// the server answers, so every run starts from the same synthetic data whatever order Playwright uses.
// Runs from api/ with DATABASE_URL already pointing at canyon_e2e (see playwright.config.ts).
import { spawn, spawnSync } from "node:child_process";

const uv = process.env.UV || "uv"; // set UV to uv's full path if it isn't on PATH
const step = (...args) => {
  const r = spawnSync(uv, ["run", ...args], { stdio: "inherit", shell: true });
  if (r.status !== 0) process.exit(r.status ?? 1);
};

step("python", "-m", "scripts.create_databases"); // creates canyon_e2e the first time
step("alembic", "upgrade", "head");
step("python", "-m", "scripts.seed"); // wipes and reseeds; refuses anything but localhost

const port = process.env.API_PORT;
spawn(uv, ["run", "fastapi", "run", "app/main.py", "--port", port], { stdio: "inherit", shell: true }).on("exit", (code) =>
  process.exit(code ?? 0),
);
