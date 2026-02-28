"""
Tests for routes/admin.py — user management and agency assignment endpoints.

Covers: list users, get user, set agencies, list agencies,
        set role, invite user.
All admin-only — non-admin users get 403.
"""
import json

from models.user import User
from models.prompt import Prompt
from models.user_agency import UserAgency


class TestListUsers:
    """Tests for GET /api/admin/users."""

    def test_requires_admin(self, client, auth_headers):
        """Non-admin returns 403."""
        headers = auth_headers("user@plmediaagency.com", "user")
        resp = client.get("/api/admin/users", headers=headers)
        assert resp.status_code == 403

    def test_requires_auth(self, client):
        """No token returns 401."""
        resp = client.get("/api/admin/users")
        assert resp.status_code == 401

    def test_list_users_as_admin(self, client, auth_headers, db_session):
        """Admin can list all users with their agency assignments."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        resp = client.get("/api/admin/users", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1
        # Each user should have an agencies array
        assert "agencies" in data[0]

    def test_list_includes_agency_assignments(self, client, auth_headers, make_user, db_session):
        """Users with agency assignments show them in the response."""
        user = make_user(
            email="assigned@plmediaagency.com", role="user", google_id="g-assigned"
        )
        ua = UserAgency(user_id=user.id, agency="Test Agency", opportunity="Michigan")
        db_session.add(ua)
        db_session.flush()

        headers = auth_headers("admin2@plmediaagency.com", "admin")
        resp = client.get("/api/admin/users", headers=headers)
        data = resp.get_json()

        assigned_user = next((u for u in data if u["email"] == "assigned@plmediaagency.com"), None)
        assert assigned_user is not None
        assert len(assigned_user["agencies"]) == 1
        assert assigned_user["agencies"][0]["agency"] == "Test Agency"
        assert assigned_user["agencies"][0]["opportunity"] == "Michigan"


class TestGetUser:
    """Tests for GET /api/admin/users/:id."""

    def test_get_user_not_found(self, client, auth_headers):
        """GET nonexistent user returns 404."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        resp = client.get("/api/admin/users/9999", headers=headers)
        assert resp.status_code == 404

    def test_get_user_as_admin(self, client, auth_headers, make_user, db_session):
        """Admin can get a single user."""
        user = make_user(email="single@plmediaagency.com", role="user", google_id="g-single")
        headers = auth_headers("admin3@plmediaagency.com", "admin")
        resp = client.get(f"/api/admin/users/{user.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["email"] == "single@plmediaagency.com"
        assert "agencies" in data


class TestSetUserAgencies:
    """Tests for PUT /api/admin/users/:id/agencies."""

    def test_set_agencies(self, client, auth_headers, make_user, db_session):
        """Admin can set a user's agency assignments."""
        user = make_user(email="target@plmediaagency.com", role="user", google_id="g-target")
        headers = auth_headers("admin4@plmediaagency.com", "admin")

        resp = client.put(
            f"/api/admin/users/{user.id}/agencies",
            data=json.dumps({
                "agencies": [
                    {"agency": "Agency A", "opportunity": "Michigan"},
                    {"agency": "Agency A", "opportunity": "Ohio"},
                    {"agency": "Agency B"},
                ]
            }),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["agencies"]) == 3

    def test_replaces_existing_assignments(self, client, auth_headers, make_user, db_session):
        """PUT replaces all existing assignments."""
        user = make_user(email="replace@plmediaagency.com", role="user", google_id="g-replace")

        # Add initial assignment
        ua = UserAgency(user_id=user.id, agency="Old Agency")
        db_session.add(ua)
        db_session.flush()

        headers = auth_headers("admin5@plmediaagency.com", "admin")

        resp = client.put(
            f"/api/admin/users/{user.id}/agencies",
            data=json.dumps({
                "agencies": [{"agency": "New Agency"}]
            }),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["agencies"]) == 1
        assert data["agencies"][0]["agency"] == "New Agency"

        # Verify old assignment is gone
        old = UserAgency.query.filter_by(user_id=user.id, agency="Old Agency").first()
        assert old is None

    def test_missing_agencies_array(self, client, auth_headers, make_user, db_session):
        """PUT without agencies array returns 400."""
        user = make_user(email="noarr@plmediaagency.com", role="user", google_id="g-noarr")
        headers = auth_headers("admin6@plmediaagency.com", "admin")
        resp = client.put(
            f"/api/admin/users/{user.id}/agencies",
            data=json.dumps({}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 400

    def test_user_not_found(self, client, auth_headers):
        """PUT on nonexistent user returns 404."""
        headers = auth_headers("admin7@plmediaagency.com", "admin")
        resp = client.put(
            "/api/admin/users/9999/agencies",
            data=json.dumps({"agencies": []}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_requires_admin(self, client, auth_headers, make_user, db_session):
        """Non-admin cannot set agencies."""
        user = make_user(email="victim@plmediaagency.com", role="user", google_id="g-victim")
        headers = auth_headers("normie@plmediaagency.com", "user")
        resp = client.put(
            f"/api/admin/users/{user.id}/agencies",
            data=json.dumps({"agencies": [{"agency": "Sneaky"}]}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 403


class TestListAgencies:
    """Tests for GET /api/admin/agencies."""

    def test_list_agencies_empty(self, client, auth_headers):
        """Returns empty list when no prompts have agency set."""
        headers = auth_headers("admin8@plmediaagency.com", "admin")
        resp = client.get("/api/admin/agencies", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_distinct_agencies(self, client, auth_headers, db_session):
        """Returns distinct agency values from prompts."""
        db_session.add(Prompt(
            prompt_type="source-list", name="SL1", prompt_text="t",
            agency="Agency Alpha", created_by="test",
        ))
        db_session.add(Prompt(
            prompt_type="source-list", name="SL2", prompt_text="t",
            agency="Agency Alpha", created_by="test",
        ))
        db_session.add(Prompt(
            prompt_type="source-list", name="SL3", prompt_text="t",
            agency="Agency Beta", created_by="test",
        ))
        db_session.flush()

        headers = auth_headers("admin9@plmediaagency.com", "admin")
        resp = client.get("/api/admin/agencies", headers=headers)
        data = resp.get_json()
        assert "Agency Alpha" in data
        assert "Agency Beta" in data
        assert len(data) == 2

    def test_requires_admin(self, client, auth_headers):
        """Non-admin returns 403."""
        headers = auth_headers("normie2@plmediaagency.com", "user")
        resp = client.get("/api/admin/agencies", headers=headers)
        assert resp.status_code == 403


class TestSetUserRole:
    """Tests for PUT /api/admin/users/:id/role."""

    def test_set_role_to_admin(self, client, auth_headers, make_user, db_session):
        """Admin can promote a user to admin."""
        user = make_user(email="promote@plmediaagency.com", role="user", google_id="g-promote")
        headers = auth_headers("admin-role@plmediaagency.com", "admin")
        resp = client.put(
            f"/api/admin/users/{user.id}/role",
            data=json.dumps({"role": "admin"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["role"] == "admin"

    def test_set_role_to_user(self, client, auth_headers, make_user, db_session):
        """Admin can demote an admin to user."""
        user = make_user(email="demote@plmediaagency.com", role="admin", google_id="g-demote")
        headers = auth_headers("admin-role2@plmediaagency.com", "admin")
        resp = client.put(
            f"/api/admin/users/{user.id}/role",
            data=json.dumps({"role": "user"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["role"] == "user"

    def test_invalid_role(self, client, auth_headers, make_user, db_session):
        """Invalid role value returns 400."""
        user = make_user(email="badrole@plmediaagency.com", role="user", google_id="g-badrole")
        headers = auth_headers("admin-role3@plmediaagency.com", "admin")
        resp = client.put(
            f"/api/admin/users/{user.id}/role",
            data=json.dumps({"role": "superadmin"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 400

    def test_missing_role(self, client, auth_headers, make_user, db_session):
        """Missing role field returns 400."""
        user = make_user(email="norole@plmediaagency.com", role="user", google_id="g-norole")
        headers = auth_headers("admin-role4@plmediaagency.com", "admin")
        resp = client.put(
            f"/api/admin/users/{user.id}/role",
            data=json.dumps({}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 400

    def test_user_not_found(self, client, auth_headers):
        """PUT on nonexistent user returns 404."""
        headers = auth_headers("admin-role5@plmediaagency.com", "admin")
        resp = client.put(
            "/api/admin/users/9999/role",
            data=json.dumps({"role": "admin"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_requires_admin(self, client, auth_headers, make_user, db_session):
        """Non-admin cannot change roles."""
        user = make_user(email="roleuser@plmediaagency.com", role="user", google_id="g-roleuser")
        headers = auth_headers("normie-role@plmediaagency.com", "user")
        resp = client.put(
            f"/api/admin/users/{user.id}/role",
            data=json.dumps({"role": "admin"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 403


class TestInviteUser:
    """Tests for POST /api/admin/users/invite."""

    def test_invite_user(self, client, auth_headers, db_session):
        """Admin can pre-invite a user by email."""
        headers = auth_headers("admin-inv@plmediaagency.com", "admin")
        resp = client.post(
            "/api/admin/users/invite",
            data=json.dumps({"email": "newguy@plmediaagency.com", "role": "user"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["email"] == "newguy@plmediaagency.com"
        assert data["role"] == "user"
        assert data["google_id"] is None

    def test_invite_as_admin_role(self, client, auth_headers, db_session):
        """Can invite a user with admin role."""
        headers = auth_headers("admin-inv2@plmediaagency.com", "admin")
        resp = client.post(
            "/api/admin/users/invite",
            data=json.dumps({"email": "newadmin@plmediaagency.com", "role": "admin"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.get_json()["role"] == "admin"

    def test_duplicate_email(self, client, auth_headers, make_user, db_session):
        """Inviting an already-registered email returns 409."""
        make_user(email="exists@plmediaagency.com", role="user", google_id="g-exists")
        headers = auth_headers("admin-inv3@plmediaagency.com", "admin")
        resp = client.post(
            "/api/admin/users/invite",
            data=json.dumps({"email": "exists@plmediaagency.com", "role": "user"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 409

    def test_missing_email(self, client, auth_headers):
        """Missing email returns 400."""
        headers = auth_headers("admin-inv4@plmediaagency.com", "admin")
        resp = client.post(
            "/api/admin/users/invite",
            data=json.dumps({"role": "user"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 400

    def test_invalid_email(self, client, auth_headers):
        """Email without @ returns 400."""
        headers = auth_headers("admin-inv5@plmediaagency.com", "admin")
        resp = client.post(
            "/api/admin/users/invite",
            data=json.dumps({"email": "notanemail", "role": "user"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 400

    def test_invalid_role(self, client, auth_headers):
        """Invalid role returns 400."""
        headers = auth_headers("admin-inv6@plmediaagency.com", "admin")
        resp = client.post(
            "/api/admin/users/invite",
            data=json.dumps({"email": "test@plmediaagency.com", "role": "superuser"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 400

    def test_requires_admin(self, client, auth_headers):
        """Non-admin cannot invite."""
        headers = auth_headers("normie-inv@plmediaagency.com", "user")
        resp = client.post(
            "/api/admin/users/invite",
            data=json.dumps({"email": "someone@plmediaagency.com", "role": "user"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 403


class TestPreInvitedLogin:
    """Tests that pre-invited users get linked on Google login."""

    def test_invited_user_claimed_on_login(self, client, app, db_session, mock_verify_google_token):
        """Pre-invited user gets google_id and keeps pre-assigned role on first login."""
        from models.user_agency import UserAgency

        # Create pre-invited user with admin role and agency
        invited = User(email="testuser@plmediaagency.com", role="admin")
        db_session.add(invited)
        db_session.flush()
        ua = UserAgency(user_id=invited.id, agency="Test Agency")
        db_session.add(ua)
        db_session.flush()

        # Login via Google — mock returns email testuser@plmediaagency.com
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({"token": "fake-google-token"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["email"] == "testuser@plmediaagency.com"
        assert data["user"]["role"] == "admin"  # Kept pre-assigned role

        # Verify google_id was set
        user = User.query.filter_by(email="testuser@plmediaagency.com").first()
        assert user.google_id == "google-test-sub-123"
        assert user.display_name == "Test User"

        # Verify agency assignment survived
        assert len(user.agencies) == 1
        assert user.agencies[0].agency == "Test Agency"
