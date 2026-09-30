from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text

from app.auth import DB
from app.errors import FieldError, field_error_handler, validation_error_handler
from app.jobs.endpoint import jobs_router
from app.routers import auth, carriers, dev, history, notifications, partners, progress, referrals, team, users, views

app = FastAPI(title="Canyon State API", version="0.1.0")
app.add_exception_handler(FieldError, field_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.include_router(partners.router)
app.include_router(referrals.router)
app.include_router(users.router)
app.include_router(views.router)
app.include_router(carriers.router)
app.include_router(progress.router)
app.include_router(notifications.router)
app.include_router(history.router)
app.include_router(auth.router)
app.include_router(team.router)
app.include_router(dev.router)

# Inngest's endpoint, only where it's configured (see app/jobs/endpoint.py).
if jobs := jobs_router():
    app.include_router(jobs)


@app.get("/health")
async def health(db: DB) -> dict[str, str]:
    await db.execute(text("select 1"))
    return {"status": "ok", "database": "ok"}
