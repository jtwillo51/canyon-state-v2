from fastapi import FastAPI
from sqlalchemy import text

from app.auth import DB
from app.routers import dev, partners, referrals

app = FastAPI(title="Canyon State API", version="0.1.0")
app.include_router(partners.router)
app.include_router(referrals.router)
app.include_router(dev.router)


@app.get("/health")
async def health(db: DB) -> dict[str, str]:
    await db.execute(text("select 1"))
    return {"status": "ok", "database": "ok"}
