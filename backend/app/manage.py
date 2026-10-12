"""Administrator maintenance: python -m app.manage reset-password."""

import argparse
import getpass

from sqlalchemy import delete, select

from .auth import hash_password
from .config import settings
from .db import Audit, AuthSession, SessionLocal, User


def main():
    parser = argparse.ArgumentParser(description="SanketAI administrator maintenance")
    parser.add_argument("command", choices=["reset-password"])
    parser.add_argument("--email", default=settings().admin_email)
    args = parser.parse_args()
    password = getpass.getpass("New password (at least 12 characters): ")
    if len(password) < 12 or password != getpass.getpass("Confirm new password: "):
        parser.error("Passwords must match and contain at least 12 characters")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == args.email.lower()))
        if not user:
            parser.error("Administrator account was not found")
        user.password_hash = hash_password(password)
        db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
        db.add(Audit(actor=user.id, event="auth.password_reset", entity_id=user.id, details={"sessions_revoked": True}))
        db.commit()
    print("Password updated; existing sessions were revoked.")


if __name__ == "__main__":
    main()
