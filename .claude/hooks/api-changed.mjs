// PostToolUse hook: after an edit to the API's contract (schemas, models, routers, main), remind Claude of
// the two things that silently go stale:
// - the generated TypeScript client (web/src/lib/api/schema.d.ts), regenerated from the running API
// - the access matrix (api/tests/test_access_matrix.py), which needs a row for every new endpoint
// Advice only: it adds context, it never blocks.
const input = JSON.parse(await new Promise((resolve) => {
  let data = "";
  process.stdin.on("data", (chunk) => (data += chunk)).on("end", () => resolve(data || "{}"));
}));
const args = input.tool_input ?? {};
const file = String(args.file_path ?? "").replace(/\\/g, "/");

if (!/\/api\/app\/(schemas|models|main)\.py$|\/api\/app\/routers\/[^/]+\.py$/.test(file)) process.exit(0);

const written = [args.content, args.new_string, ...(args.edits ?? []).map((e) => e.new_string)].join("\n");
const notes = [
  "The API contract changed. Before finishing: with the API running, `npm run gen:api` in web/ regenerates " +
    "web/src/lib/api/schema.d.ts (committed), then `npm run typecheck` shows what the change broke in the web app.",
];
if (/@(router|app)\.(get|post|put|patch|delete)\(/.test(written)) {
  notes.push(
    "An endpoint was added or changed: give it a row in CASES in api/tests/test_access_matrix.py (who may call it: " +
      "nobody / owner / other rep / admin), or the guard test fails. If what's inside the response differs by " +
      "viewer, add a content test too; the matrix only checks status codes.",
  );
}
console.log(JSON.stringify({ hookSpecificOutput: { hookEventName: "PostToolUse", additionalContext: notes.join("\n") } }));
