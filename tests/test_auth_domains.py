"""
Tests for auth domain validation — all allowed domains and emails.

Covers: plmediaagency.com, locallabs.com, projectroseland.com,
specific allowed emails, rejected domains, case insensitivity.
"""
from services.auth_service import get_or_create_user, ALLOWED_DOMAINS, ALLOWED_EMAILS

import pytest


class TestAllowedDomains:
    """Verify all configured domains are accepted."""

    def test_plmediaagency_domain(self, app, db_session):
        """@plmediaagency.com emails are accepted."""
        with app.app_context():
            user = get_or_create_user({
                "sub": "g-plm-1",
                "email": "user@plmediaagency.com",
                "name": "PLM User",
                "picture": "",
            })
            assert user.email == "user@plmediaagency.com"

    def test_locallabs_domain(self, app, db_session):
        """@locallabs.com emails are accepted."""
        with app.app_context():
            user = get_or_create_user({
                "sub": "g-ll-1",
                "email": "user@locallabs.com",
                "name": "LL User",
                "picture": "",
            })
            assert user.email == "user@locallabs.com"

    def test_projectroseland_domain(self, app, db_session):
        """@projectroseland.com emails are accepted."""
        with app.app_context():
            user = get_or_create_user({
                "sub": "g-pr-1",
                "email": "user@projectroseland.com",
                "name": "PR User",
                "picture": "",
            })
            assert user.email == "user@projectroseland.com"

    def test_case_insensitive_domain(self, app, db_session):
        """Domain check is case-insensitive."""
        with app.app_context():
            user = get_or_create_user({
                "sub": "g-upper-1",
                "email": "User@PLMediaAgency.COM",
                "name": "Upper",
                "picture": "",
            })
            assert user is not None

    def test_rejected_domain(self, app, db_session):
        """Non-allowed domain raises ValueError."""
        with app.app_context():
            with pytest.raises(ValueError, match="not allowed"):
                get_or_create_user({
                    "sub": "g-bad-1",
                    "email": "hacker@evil.com",
                    "name": "Bad",
                    "picture": "",
                })

    def test_gmail_not_allowed_unless_whitelisted(self, app, db_session):
        """Random gmail.com addresses are rejected."""
        with app.app_context():
            with pytest.raises(ValueError, match="not allowed"):
                get_or_create_user({
                    "sub": "g-gmail-1",
                    "email": "randomuser@gmail.com",
                    "name": "Random",
                    "picture": "",
                })


class TestAllowedEmails:
    """Verify specific whitelisted emails are accepted."""

    def test_btimpone_gmail(self, app, db_session):
        """btimpone@gmail.com is explicitly allowed."""
        with app.app_context():
            user = get_or_create_user({
                "sub": "g-bt-1",
                "email": "btimpone@gmail.com",
                "name": "BT",
                "picture": "",
            })
            assert user.email == "btimpone@gmail.com"

    def test_cashkar_gmail(self, app, db_session):
        """cashkar@gmail.com is explicitly allowed."""
        with app.app_context():
            user = get_or_create_user({
                "sub": "g-ck-1",
                "email": "cashkar@gmail.com",
                "name": "CK",
                "picture": "",
            })
            assert user.email == "cashkar@gmail.com"

    def test_allowed_emails_case_insensitive(self, app, db_session):
        """Whitelisted email check is case-insensitive."""
        with app.app_context():
            user = get_or_create_user({
                "sub": "g-bt-upper",
                "email": "BTimpone@Gmail.COM",
                "name": "BT Upper",
                "picture": "",
            })
            assert user is not None


class TestDomainListCompleteness:
    """Verify the ALLOWED_DOMAINS and ALLOWED_EMAILS lists match expectations."""

    def test_three_domains_configured(self):
        """All 3 allowed domains are in the list."""
        assert "plmediaagency.com" in ALLOWED_DOMAINS
        assert "locallabs.com" in ALLOWED_DOMAINS
        assert "projectroseland.com" in ALLOWED_DOMAINS

    def test_two_emails_configured(self):
        """Both whitelisted emails are in the list."""
        assert "btimpone@gmail.com" in ALLOWED_EMAILS
        assert "cashkar@gmail.com" in ALLOWED_EMAILS
