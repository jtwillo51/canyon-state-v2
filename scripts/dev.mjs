// `npm run dev`: everything needed to use the app locally, in one terminal.
//
// 1. Prepare the database: create it if missing, migrate, and seed only if it has no users yet.
//    All three are safe to repeat, so this runs on every start. `npm run reseed` starts the data over.
// 2. Start the API (:8000) and the web app (:3000) side by side, each line prefixed with its name.
//    Ctrl+C, or either one exiting, stops both.
//
// Needs uv, Node and a running Postgres 17, with api/.env filled in (copy api/.env.example).
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const api = `${root}api`;
const web = `${root}web`;
const isWindows = process.platform === "win32";

if (!existsSync(`${api}/.env`)) {
  console.error("api/.env is missing. Copy api/.env.example to api/.env and set your database password.");
  process.exit(1);
}

/** Run a setup step to completion; stop everything if it fails. */
function step(label, command, args, cwd) {
  console.log(`\n> ${label}`);
  const result = spawnSync(command, args, { cwd, stdio: "inherit", shell: isWindows });
  if (result.status !== 0) {
    console.error(`\n"${label}" failed. Is Postgres running, and is the password in api/.env right?`);
    process.exit(result.status ?? 1);
  }
}

if (process.argv.includes("--reseed")) {
  step("Reseeding with fresh synthetic data", "uv", ["run", "python", "-m", "scripts.seed"], api);
  process.exit(0);
}

step("Creating databases if missing", "uv", ["run", "python", "-m", "scripts.create_databases"], api);
step("Migrating to the latest schema", "uv", ["run", "alembic", "upgrade", "head"], api);
step("Seeding if empty", "uv", ["run", "python", "-m", "scripts.seed", "--if-empty"], api);
if (!existsSync(`${web}/node_modules`)) step("Installing web packages", "npm", ["install"], web);

const colors = { api: "\x1b[36m", web: "\x1b[35m" };
const children = [];
let stopping = false;

/** Start a long-running server, prefixing each line of its output with its name. */
function serve(name, command, args, cwd) {
  const child = spawn(command, args, { cwd, shell: isWindows, env: { ...process.env, FORCE_COLOR: "1" } });
  const prefix = `${colors[name]}[${name}]\x1b[0m `;
  for (const stream of [child.stdout, child.stderr]) {
    let partial = "";
    stream.on("data", (chunk) => {
      const lines = (partial + chunk).split(/\r?\n/);
      partial = lines.pop();
      for (const line of lines) process.stdout.write(prefix + line + "\n");
    });
  }
  child.on("exit", (code) => {
    if (!stopping) {
      console.log(`${prefix}exited (${code ?? "killed"}); stopping the other server.`);
      stopAll(code ?? 1);
    }
  });
  children.push(child);
}

/** Stop both servers. On Windows the shell's children (uvicorn, next) only die with the whole process tree. */
function stopAll(code = 0) {
  stopping = true;
  for (const child of children) {
    if (child.exitCode !== null) continue;
    if (isWindows) spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    else child.kill("SIGTERM");
  }
  process.exit(code);
}

process.on("SIGINT", () => stopAll(0));
process.on("SIGTERM", () => stopAll(0));

console.log("\nStarting the API on http://localhost:8000 (docs at /docs) and the web app on http://localhost:3000\n");
serve("api", "uv", ["run", "fastapi", "dev", "app/main.py", "--port", "8000"], api);
serve("web", "npm", ["run", "dev", "--", "--port", "3000"], web);
