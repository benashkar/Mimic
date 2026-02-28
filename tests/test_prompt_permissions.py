"""
Tests for permission filtering in GET /api/prompts.

Covers: admin sees all, non-admin filtered by agency/opportunity,
        PAPA/Amy Bot visible to all, wildcard opportunity access.
"""
from models.prompt import Prompt
from models.user_agency import UserAgency


class TestAdminSeesAll:
    """Admin users bypass permission filtering."""

    def test_admin_sees_all_prompts(self, client, auth_headers, db_session):
        """Admin sees every prompt regardless of agency."""
        db_session.add(Prompt(
            prompt_type="source-list", name="SL-A", prompt_text="t",
            agency="Agency A", opportunity="Michigan", created_by="test",
        ))
        db_session.add(Prompt(
            prompt_type="source-list", name="SL-B", prompt_text="t",
            agency="Agency B", opportunity="Ohio", created_by="test",
        ))
        db_session.flush()

        headers = auth_headers("admin@plmediaagency.com", "admin")
        resp = client.get("/api/prompts", headers=headers)
        data = resp.get_json()
        names = [p["name"] for p in data]
        assert "SL-A" in names
        assert "SL-B" in names


class TestNonAdminFiltering:
    """Non-admin users filtered by agency/opportunity assignments."""

    def test_user_sees_only_assigned_agency(self, client, make_user, db_session, app):
        """User with one agency only sees prompts from that agency."""
        from services.auth_service import generate_jwt

        user = make_user(email="perm1@plmediaagency.com", role="user", google_id="g-perm1")
        ua = UserAgency(user_id=user.id, agency="Agency A")
        db_session.add(ua)

        db_session.add(Prompt(
            prompt_type="source-list", name="Visible", prompt_text="t",
            agency="Agency A", opportunity="Michigan", created_by="test",
        ))
        db_session.add(Prompt(
            prompt_type="source-list", name="Hidden", prompt_text="t",
            agency="Agency B", opportunity="Ohio", created_by="test",
        ))
        db_session.flush()

        with app.app_context():
            token = generate_jwt(user)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/prompts", headers=headers)
        data = resp.get_json()
        names = [p["name"] for p in data]
        assert "Visible" in names
        assert "Hidden" not in names

    def test_user_with_specific_opportunity(self, client, make_user, db_session, app):
        """User assigned to specific opportunity only sees that one."""
        from services.auth_service import generate_jwt

        user = make_user(email="perm2@plmediaagency.com", role="user", google_id="g-perm2")
        ua = UserAgency(user_id=user.id, agency="Agency A", opportunity="Michigan")
        db_session.add(ua)

        db_session.add(Prompt(
            prompt_type="source-list", name="MI Prompt", prompt_text="t",
            agency="Agency A", opportunity="Michigan", created_by="test",
        ))
        db_session.add(Prompt(
            prompt_type="source-list", name="OH Prompt", prompt_text="t",
            agency="Agency A", opportunity="Ohio", created_by="test",
        ))
        db_session.flush()

        with app.app_context():
            token = generate_jwt(user)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/prompts", headers=headers)
        data = resp.get_json()
        names = [p["name"] for p in data]
        assert "MI Prompt" in names
        assert "OH Prompt" not in names

    def test_wildcard_opportunity_sees_all_in_agency(self, client, make_user, db_session, app):
        """User with NULL opportunity sees all opportunities in that agency."""
        from services.auth_service import generate_jwt

        user = make_user(email="perm3@plmediaagency.com", role="user", google_id="g-perm3")
        ua = UserAgency(user_id=user.id, agency="Agency A")  # no opportunity = wildcard
        db_session.add(ua)

        db_session.add(Prompt(
            prompt_type="source-list", name="MI", prompt_text="t",
            agency="Agency A", opportunity="Michigan", created_by="test",
        ))
        db_session.add(Prompt(
            prompt_type="source-list", name="OH", prompt_text="t",
            agency="Agency A", opportunity="Ohio", created_by="test",
        ))
        db_session.flush()

        with app.app_context():
            token = generate_jwt(user)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/prompts", headers=headers)
        data = resp.get_json()
        names = [p["name"] for p in data]
        assert "MI" in names
        assert "OH" in names

    def test_papa_visible_to_all_users(self, client, make_user, db_session, app):
        """PAPA/PSST prompts are visible even without agency assignment."""
        from services.auth_service import generate_jwt

        user = make_user(email="perm4@plmediaagency.com", role="user", google_id="g-perm4")
        # No agency assignments

        db_session.add(Prompt(
            prompt_type="papa", name="PAPA Prompt", prompt_text="t",
            created_by="test",
        ))
        db_session.add(Prompt(
            prompt_type="source-list", name="Restricted SL", prompt_text="t",
            agency="Agency X", created_by="test",
        ))
        db_session.flush()

        with app.app_context():
            token = generate_jwt(user)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/prompts", headers=headers)
        data = resp.get_json()
        names = [p["name"] for p in data]
        assert "PAPA Prompt" in names
        assert "Restricted SL" not in names

    def test_amy_bot_visible_to_all_users(self, client, make_user, db_session, app):
        """Amy Bot prompts are visible to all authenticated users."""
        from services.auth_service import generate_jwt

        user = make_user(email="perm5@plmediaagency.com", role="user", google_id="g-perm5")

        db_session.add(Prompt(
            prompt_type="amy-bot", name="Amy Bot", prompt_text="t",
            created_by="test",
        ))
        db_session.flush()

        with app.app_context():
            token = generate_jwt(user)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/prompts", headers=headers)
        data = resp.get_json()
        names = [p["name"] for p in data]
        assert "Amy Bot" in names

    def test_case_insensitive_agency_match(self, client, make_user, db_session, app):
        """Agency matching is case-insensitive."""
        from services.auth_service import generate_jwt

        user = make_user(email="perm6@plmediaagency.com", role="user", google_id="g-perm6")
        ua = UserAgency(user_id=user.id, agency="agency a")
        db_session.add(ua)

        db_session.add(Prompt(
            prompt_type="source-list", name="Case Test", prompt_text="t",
            agency="Agency A", opportunity="Michigan", created_by="test",
        ))
        db_session.flush()

        with app.app_context():
            token = generate_jwt(user)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/prompts", headers=headers)
        data = resp.get_json()
        names = [p["name"] for p in data]
        assert "Case Test" in names


class TestAgencyQueryFilter:
    """Tests for the ?agency= query param on GET /api/prompts."""

    def test_filter_by_agency_param(self, client, auth_headers, db_session):
        """Can filter prompts by agency query parameter."""
        db_session.add(Prompt(
            prompt_type="source-list", name="SL-Alpha", prompt_text="t",
            agency="Alpha Corp", created_by="test",
        ))
        db_session.add(Prompt(
            prompt_type="source-list", name="SL-Beta", prompt_text="t",
            agency="Beta Inc", created_by="test",
        ))
        db_session.flush()

        headers = auth_headers("admin@plmediaagency.com", "admin")
        resp = client.get("/api/prompts?agency=Alpha", headers=headers)
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["name"] == "SL-Alpha"
