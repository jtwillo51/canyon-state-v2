from fastapi import FastAPI
from sqlalchemy import text

from app.auth import DB
from app.errors import FieldError, field_error_handler
from app.routers import dev, partners, referrals, users, views

app = FastAPI(title="Canyon State API", version="0.1.0")
app.add_exception_handler(FieldError, field_error_handler)
app.include_router(partners.router)
app.include_router(referrals.router)
app.include_router(users.router)
app.include_router(views.router)
app.include_router(dev.router)


@app.get("/health")
async def health(db: DB) -> dict[str, str]:
    await db.execute(text("select 1"))
    return {"status": "ok", "database": "ok"}
