"""
Tests for services/auth_service.py.

Covers: domain validation, first-user admin, JWT roundtrip, expired JWT.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import jwt
import pytest

from services.auth_service import (
    get_or_create_user,
    generate_jwt,
    decode_jwt,
    verify_google_token,
)
from models.user import User


VALID_CLAIMS = {
    "sub": "google-abc-123",
    "email": "alice@plmediaagency.com",
    "name": "Alice",
    "picture": "https://example.com/alice.jpg",
}


class TestGetOrCreateUser:
    """Tests for get_or_create_user."""

    def test_valid_domain_creates_user(self, app, db_session):
        """plmediaagency.com email creates a user successfully."""
        with app.app_context():
            user = get_or_create_user(VALID_CLAIMS)
            assert user.email == "alice@plmediaagency.com"
            assert user.google_id == "google-abc-123"

    def test_locallabs_domain_creates_user(self, app, db_session):
        """locallabs.com email creates a user successfully."""
        with app.app_context():
            ll_claims = {**VALID_CLAIMS, "sub": "google-ll-789", "email": "carol@locallabs.com"}
            user = get_or_create_user(ll_claims)
            assert user.email == "carol@locallabs.com"

    def test_wrong_domain_raises(self, app, db_session):
        """Non-allowed domain raises ValueError."""
        bad_claims = {**VALID_CLAIMS, "email": "bob@gmail.com"}
        with app.app_context():
            with pytest.raises(ValueError, match="not allowed"):
                get_or_create_user(bad_claims)

    def test_first_user_is_admin(self, app, db_session):
        """The very first user created gets role='admin'."""
        with app.app_context():
            user = get_or_create_user(VALID_CLAIMS)
            assert user.role == "admin"

    def test_second_user_is_regular(self, app, db_session):
        """Subsequent users get role='user'."""
        with app.app_context():
            get_or_create_user(VALID_CLAIMS)
            second_claims = {
                **VALID_CLAIMS,
                "sub": "google-xyz-456",
                "email": "bob@plmediaagency.com",
            }
            second = get_or_create_user(second_claims)
            assert second.role == "user"

    def test_existing_user_updates_last_login(self, app, db_session):
        """Logging in again updates last_login_at without creating a duplicate."""
        with app.app_context():
            user1 = get_or_create_user(VALID_CLAIMS)
            first_login = user1.last_login_at
            user2 = get_or_create_user(VALID_CLAIMS)
            assert user1.id == user2.id
            assert user2.last_login_at >= first_login


class TestJWT:
    """Tests for generate_jwt and decode_jwt."""

    def test_roundtrip(self, app, db_session, make_user):
        """Generate then decode returns same claims."""
        with app.app_context():
            user = make_user()
            token = generate_jwt(user)
            claims = decode_jwt(token)
            assert claims["sub"] == user.email
            assert claims["role"] == user.role
            assert claims["user_id"] == user.id

    def test_expired_jwt_returns_none(self, app, db_session, make_user):
        """An expired JWT decodes to None."""
        with app.app_context():
            user = make_user()
            payload = {
                "sub": user.email,
                "role": user.role,
                "user_id": user.id,
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            }
            expired_token = jwt.encode(
                payload, app.config["SECRET_KEY"], algorithm="HS256"
            )
            assert decode_jwt(expired_token) is None


class TestVerifyGoogleToken:
    """Tests for verify_google_token (mocked)."""

    def test_returns_claims(self, app, mock_verify_google_token):
        """verify_google_token returns structured claims from Google."""
        with app.app_context():
            result = verify_google_token("fake-id-token")
            assert result["email"] == "testuser@plmediaagency.com"
            assert result["sub"] == "google-test-sub-123"
