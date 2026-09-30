// Where the end-to-end stack lives. Its own ports and its own database, so a run never touches
// `npm run dev`, the dev API, or canyon_dev.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

export const API_PORT = 8100;
export const WEB_PORT = 3100;
export const API_URL = `http://localhost:${API_PORT}`;
export const WEB_URL = `http://localhost:${WEB_PORT}`;

/** The dev DATABASE_URL (env, else api/.env) with the database swapped for canyon_e2e. Local only. */
export function e2eDatabaseUrl(): string {
  const base = process.env.DATABASE_URL ?? readDotenv(resolve(__dirname, "../../api/.env")).DATABASE_URL;
  if (!base) throw new Error("Set DATABASE_URL or create api/.env (see api/.env.example)");
  const url = new URL(base);
  if (!["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) {
    throw new Error(`e2e tests reseed their database, so it must be local, not ${url.hostname}`);
  }
  url.pathname = "/canyon_e2e";
  return url.toString();
}

function readDotenv(path: string): Record<string, string> {
  const lines = readFileSync(path, "utf8").split(/\r?\n/);
  return Object.fromEntries(
    lines
      .map((line) => line.match(/^\s*([A-Z_]+)\s*=\s*(.*?)\s*$/))
      .filter((m): m is RegExpMatchArray => m !== null)
      .map(([, key, value]) => [key, value.replace(/^["']|["']$/g, "")]),
  );
}
