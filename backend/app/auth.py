import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import AuthSession, User, get_db, now

COOKIE = "sanket_session"


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password, encoded):
    _, salt, _ = encoded.split("$")
    return hmac.compare_digest(hash_password(password, salt), encoded)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def bootstrap_admin(db):
    config = settings()
    if db.scalar(select(User).limit(1)) is None:
        if not config.admin_password:
            raise RuntimeError("Set SANKET_ADMIN_PASSWORD (at least 12 characters) before first startup")
        db.add(User(email=config.admin_email.lower(), password_hash=hash_password(config.admin_password)))
        db.commit()


def current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE, "")
    session = db.get(AuthSession, token_hash(token)) if token else None
    if session is None or session.expires_at.replace(tzinfo=now().tzinfo) <= now():
        raise HTTPException(401, "Please sign in to your workspace")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(csrf, session.csrf):
            raise HTTPException(403, "Invalid CSRF token. Refresh and try again.")
        origin = request.headers.get("origin")
        if origin and origin != settings().frontend_origin:
            raise HTTPException(403, "Untrusted request origin")
    request.state.auth_session = session
    return db.get(User, session.user_id)


def new_session(db, user):
    token = secrets.token_urlsafe(48)
    session = AuthSession(
        token_hash=token_hash(token),
        user_id=user.id,
        csrf=secrets.token_hex(32),
        expires_at=now() + timedelta(hours=settings().session_hours),
    )
    db.add(session)
    return token, session
