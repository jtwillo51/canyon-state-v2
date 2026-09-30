"""Print a one-time setup or reset link for someone, from the server's own shell. Creates them as an admin first
if they don't exist yet.

This is how the very first admin gets in on a fresh deployment (the Team page needs an admin to already be
signed in), and a way back in if every admin is locked out. It's run by whoever has shell access to the API's
server, which is already the most privileged position there is, so it grants nothing new.

Run from api/:
    uv run python -m scripts.make_link dana@example.test --name "Dana Whitfield" --site https://app.example.com
"""

import argparse
import asyncio
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.audit import Actor, set_actor
from app.db import SessionLocal, engine
from app.models import AccountLink, User
from app.routers.team import LINK_LIFETIME
from app.security import new_token, token_hash


async def main(email: str, name: str | None, site: str) -> None:
    async with SessionLocal() as db:
        set_actor(db, Actor.script("make_link"))
        user = (await db.execute(select(User).where(func.lower(User.email) == email.strip().lower()))).scalar_one_or_none()
        if user is None:
            if not name:
                raise SystemExit(f"No one uses {email} yet. Add --name to create them as an admin.")
            user = User(name=name.strip(), email=email.strip().lower(), role="admin")
            db.add(user)
            await db.flush()
            print(f"Created {user.name} as an admin.")
        elif not user.active:
            raise SystemExit(f"{user.name} is deactivated. Reactivate them first.")

        now = datetime.now(UTC)
        for old in (await db.execute(select(AccountLink).where(AccountLink.user_id == user.id, AccountLink.used_at.is_(None), AccountLink.voided_at.is_(None)))).scalars():
            old.voided_at = now
        token = new_token()
        purpose = "reset" if user.password_hash else "setup"
        db.add(AccountLink(user_id=user.id, purpose=purpose, token_hash=token_hash(token), expires_at=now + LINK_LIFETIME, created_by_id=user.id))
        await db.commit()
    await engine.dispose()
    print(f"One-time {purpose} link for {user.name} (works once, for {LINK_LIFETIME.total_seconds() / 3600:.0f} hours):")
    print(f"  {site.rstrip('/')}/set-password#token={token}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("email")
    parser.add_argument("--name", help="create them (as an admin) if they don't exist yet")
    parser.add_argument("--site", default="http://localhost:3000", help="the web app's address")
    args = parser.parse_args()
    asyncio.run(main(args.email, args.name, args.site))
