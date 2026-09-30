// PreToolUse hook: keep Claude away from secrets and real agency data.
// - Nothing under a `private-data` folder is read, searched, edited or named in a shell command. That's
//   where the agency's real partner and client records would live (git-ignored, local only).
// - `.env` files (real credentials) are never edited. `.env.example` is fine: it holds no secrets.
// Denies with a reason Claude sees; anything else passes through untouched.
import { basename } from "node:path";

const input = JSON.parse(await new Promise((resolve) => {
  let data = "";
  process.stdin.on("data", (chunk) => (data += chunk)).on("end", () => resolve(data || "{}"));
}));
const tool = input.tool_name ?? "";
const args = input.tool_input ?? {};

const PRIVATE = /(^|[\\/\s"'=])private-data([\\/\s"']|$)/i;
const isEnv = (p) => /^\.env(\..+)?$/i.test(basename(p)) && !/\.example$/i.test(p);

function deny(reason) {
  console.log(JSON.stringify({
    hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: reason },
  }));
  process.exit(0);
}

// Every path-like argument the file tools take.
const paths = [args.file_path, args.path, args.notebook_path, args.pattern, args.glob].filter((v) => typeof v === "string");
const command = typeof args.command === "string" ? args.command : "";

if (paths.some((p) => PRIVATE.test(p)) || PRIVATE.test(command)) {
  deny("private-data holds the agency's real records and is off limits to Claude. Use the synthetic seed (api/scripts/seed.py) instead; ask the user if real data is truly needed.");
}
if (["Edit", "Write", "MultiEdit", "NotebookEdit"].includes(tool) && paths.some(isEnv)) {
  deny(".env files hold real credentials and are edited by the user only. Change .env.example (no secrets) and tell the user what to set.");
}
