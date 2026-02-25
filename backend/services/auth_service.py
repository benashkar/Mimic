"""
Auth service — Google token verification, user management, JWT.

Handles the full login flow:
  1. Verify Google ID token
  2. Domain check (@plmediaagency.com and @locallabs.com)
  3. Create or fetch user (first user = admin)
  4. Issue/decode JWT session tokens
"""
import logging
from datetime import datetime, timezone, timedelta

import jwt
from flask import current_app
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from models import db
from models.user import User

logger = logging.getLogger(__name__)

ALLOWED_DOMAINS = ["plmediaagency.com", "locallabs.com"]
ALLOWED_EMAILS = ["btimpone@gmail.com", "cashkar@gmail.com"]


def verify_google_token(id_token_str):
    """
    Validate a Google ID token and return claims.

    Returns:
        dict with keys: sub, email, name, picture
    Raises:
        ValueError: if token is invalid or expired
    """
    claims = id_token.verify_oauth2_token(
        id_token_str,
        google_requests.Request(),
        current_app.config["GOOGLE_CLIENT_ID"],
    )
    return {
        "sub": claims["sub"],
        "email": claims["email"],
        "name": claims.get("name") or "",
        "picture": claims.get("picture") or "",
    }


def get_or_create_user(google_claims):
    """
    Find existing user by google_id or create a new one.

    Domain check: only @plmediaagency.com and @locallabs.com emails allowed.
    First user in the database automatically gets admin role.

    Args:
        google_claims: dict from verify_google_token

    Returns:
        User instance

    Raises:
        ValueError: if email domain is not allowed
    """
    email = google_claims["email"]

    # Allow specific emails or allowed domains — .lower() both sides
    email_lower = email.lower()
    domain = email_lower.split("@")[-1]
    if email_lower not in [e.lower() for e in ALLOWED_EMAILS] and domain not in [d.lower() for d in ALLOWED_DOMAINS]:
        logger.error("[ERR] Invalid domain: %s", email)
        raise ValueError(f"Email domain @{domain} is not allowed")

    user = User.query.filter_by(google_id=google_claims["sub"]).first()

    if user:
        user.last_login_at = datetime.now(timezone.utc)
        db.session.commit()
        logger.info("[OK] User logged in: %s", email)
        return user

    # First user in the system becomes admin
    is_first_user = User.query.count() == 0
    role = "admin" if is_first_user else "user"

    user = User(
        google_id=google_claims["sub"],
        email=email,
        display_name=google_claims.get("name") or "",
        avatar_url=google_claims.get("picture") or "",
        role=role,
        last_login_at=datetime.now(timezone.utc),
    )
    db.session.add(user)
    db.session.commit()
    logger.info("[OK] User logged in: %s (role=%s, new=True)", email, role)
    return user


def generate_jwt(user):
    """
    Create a signed JWT for the given user.

    Payload: sub (email), role, user_id, exp (now + JWT_EXPIRY_HOURS).
    Signed with app SECRET_KEY using HS256.
    """
    expiry_hours = current_app.config.get("JWT_EXPIRY_HOURS") or 24
    payload = {
        "sub": user.email,
        "role": user.role,
        "user_id": user.id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=expiry_hours),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def decode_jwt(token):
    """
    Decode and validate a JWT.

    Returns:
        dict of claims on success, None on failure (expired, invalid, etc.)
    """
    try:
        return jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],
        )
    except jwt.PyJWTError:
        return None
