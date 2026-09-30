// `npm run dev:demo`: the dev server as the public demo looks (DEMO_MODE banner), on any OS.
import { spawn } from "node:child_process";

const port = process.env.PORT ?? "3000";
spawn("npx", ["next", "dev", "--port", port], {
  stdio: "inherit",
  shell: true,
  env: { ...process.env, DEMO_MODE: "true" },
}).on("exit", (code) => process.exit(code ?? 0));
