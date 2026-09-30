"""Write the API's OpenAPI schema to a file, without starting a server or touching a database.

CI uses it to prove the committed TypeScript client (web/src/lib/api/schema.d.ts) matches the API:
it regenerates the client from this file and fails if anything changed.

Run from api/:  uv run python -m scripts.export_openapi openapi.json
"""

import json
import sys

from app.main import app

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(app.openapi(), f, indent=2)
        f.write("\n")
    print(f"wrote {path}")
