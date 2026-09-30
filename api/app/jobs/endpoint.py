"""The HTTP endpoint Inngest calls to run the jobs (/api/inngest).

It exists only when configured (a signing key, or the local Dev Server): elsewhere the path is a plain 404,
which fails closed. In production the SDK rejects any request not signed with INNGEST_SIGNING_KEY, and
unsigned re-registration of the app ("sync") is turned off (the SDK would otherwise allow it).

It's left out of the OpenAPI schema so the API's contract, and the TypeScript client generated from it,
don't change with configuration. That makes it the one reviewed exception to the access matrix's
"every endpoint is in the schema" guard; tests/test_jobs.py covers its security instead.
"""

import inngest.fast_api
from fastapi import APIRouter

from app.config import settings
from app.jobs.functions import FUNCTIONS, client


def jobs_router() -> APIRouter | None:
    if not settings.jobs_enabled:
        return None
    router = APIRouter(include_in_schema=False)
    # serve() only uses .get/.post/.put, which a router has too.
    inngest.fast_api.serve(router, client, FUNCTIONS, enable_unauthed_sync=False)  # type: ignore[arg-type]
    return router
