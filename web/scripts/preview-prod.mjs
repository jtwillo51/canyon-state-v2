// `npm run preview:prod`: the whole app running locally exactly as the deployed demo does, to check before
// deploying. No hot reload, no dev mode:
//   - a fresh synthetic world in the local canyon_e2e database (seeded, jobs run once for notifications);
//   - the API as on Render: DEMO_MODE on, DEV_AUTH off, `fastapi run` (no auto-reload), on :8300;
//   - the web app as on Vercel: a production build served by `next start`, on http://localhost:3300.
// Ctrl+C stops both. Never touches canyon_dev or the dev servers on :3000/:8000.
import { spawn, spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

const API_PORT = 8300;
const WEB_PORT = Number(process.env.PORT ?? 3300);
const web = resolve(import.meta.dirname, "..");
const api = resolve(web, "../api");

/** uv from UV, PATH, or winget's install folder (Windows). */
function findUv() {
  if (process.env.UV) return process.env.UV;
  if (spawnSync("uv", ["--version"], { shell: true }).status === 0) return "uv";
  const pkgs = join(process.env.LOCALAPPDATA ?? "", "Microsoft/WinGet/Packages");
  const dir = existsSync(pkgs) ? readdirSync(pkgs).find((d) => d.startsWith("astral-sh.uv")) : undefined;
  if (dir && existsSync(join(pkgs, dir, "uv.exe"))) return join(pkgs, dir, "uv.exe");
  throw new Error("Can't find uv. Install it or set UV to its full path.");
}

/** The dev DATABASE_URL (env, else api/.env) pointed at canyon_e2e, and only ever a local one. */
function previewDatabaseUrl() {
  const fromFile = readFileSync(join(api, ".env"), "utf8").match(/^\s*DATABASE_URL\s*=\s*(.+?)\s*$/m)?.[1];
  const url = new URL((process.env.DATABASE_URL ?? fromFile ?? "").replace(/^["']|["']$/g, ""));
  if (!["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) throw new Error("The preview reseeds its database, so it must be local.");
  url.pathname = "/canyon_e2e";
  return url.toString();
}

const uv = findUv();
const apiEnv = { ...process.env, DATABASE_URL: previewDatabaseUrl(), DEMO_MODE: "true", DEV_AUTH: "false" };
const run = (cmd, args, opts) => {
  const r = spawnSync(cmd, args, { stdio: "inherit", shell: true, ...opts });
  if (r.status !== 0) process.exit(r.status ?? 1);
};

console.log("\n· Preparing a fresh synthetic database (canyon_e2e)…");
for (const step of [["python", "-m", "scripts.create_databases"], ["alembic", "upgrade", "head"], ["python", "-m", "scripts.seed"], ["python", "-m", "scripts.run_jobs"]]) {
  run(`"${uv}"`, ["run", ...step], { cwd: api, env: apiEnv });
}

console.log("\n· Building the web app for production…");
run("npx", ["next", "build"], { cwd: web, env: { ...process.env, API_URL: `http://localhost:${API_PORT}`, DEMO_MODE: "true" } });

console.log(`\n· Starting the API on :${API_PORT} and the web app on http://localhost:${WEB_PORT}`);
const children = [
  spawn(`"${uv}"`, ["run", "fastapi", "run", "app/main.py", "--port", String(API_PORT)], { cwd: api, env: apiEnv, stdio: "inherit", shell: true }),
  spawn("npx", ["next", "start", "-p", String(WEB_PORT)], {
    cwd: web,
    env: { ...process.env, API_URL: `http://localhost:${API_PORT}`, DEMO_MODE: "true" },
    stdio: "inherit",
    shell: true,
  }),
];
const stop = () => {
  for (const c of children) c.kill();
  process.exit(0);
};
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
for (const c of children) c.on("exit", stop);
