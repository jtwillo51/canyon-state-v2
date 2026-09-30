"""Run the API with background jobs on, for the local Inngest Dev Server.

Sets INNGEST_DEV (no request signing: local only; config refuses it without DEV_AUTH) and starts the API.
Then, in another terminal, start the Dev Server pointed at it:

    npx inngest-cli@1.45.1 dev --no-discovery -u http://localhost:8200/api/inngest

and open http://localhost:8288 to see the functions, invoke them, and watch each step.

Run from api/:  uv run python -m scripts.dev_with_jobs [port]   (default 8200)
"""

import os
import sys

import uvicorn

if __name__ == "__main__":
    os.environ["INNGEST_DEV"] = "true"
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8200
    uvicorn.run("app.main:app", host="127.0.0.1", port=port)
