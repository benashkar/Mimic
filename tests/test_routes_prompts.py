"""
Tests for routes/prompts.py — Prompt Library CRUD.

Covers: list, filter, get, create (admin), create (user → 403),
        update, delete (soft-delete).
"""
import json


class TestListPrompts:
    """Tests for GET /api/prompts."""

    def test_list_requires_auth(self, client, db_session):
        """GET /prompts without token returns 401."""
        resp = client.get("/api/prompts")
        assert resp.status_code == 401

    def test_list_empty(self, client, db_session, auth_headers):
        """GET /prompts with no data returns empty list."""
        headers = auth_headers("list@plmediaagency.com", "user")
        resp = client.get("/api/prompts", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_with_type_filter(self, client, db_session, auth_headers, make_user):
        """GET /prompts?type=papa filters correctly."""
        from models.prompt import Prompt

        # Create prompts of different types
        db_session.add(Prompt(
            prompt_type="papa", name="PAPA", prompt_text="text",
            is_active=True, created_by="test",
        ))
        db_session.add(Prompt(
            prompt_type="amy-bot", name="Amy", prompt_text="text",
            is_active=True, created_by="test",
        ))
        db_session.flush()

        headers = auth_headers("filter@plmediaagency.com", "user")
        resp = client.get("/api/prompts?type=papa", headers=headers)
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["prompt_type"] == "papa"


class TestGetPrompt:
    """Tests for GET /api/prompts/:id."""

    def test_get_not_found(self, client, db_session, auth_headers):
        """GET /prompts/9999 returns 404."""
        headers = auth_headers("get@plmediaagency.com", "user")
        resp = client.get("/api/prompts/9999", headers=headers)
        assert resp.status_code == 404


class TestCreatePrompt:
    """Tests for POST /api/prompts."""

    def test_create_as_admin(self, client, db_session, auth_headers):
        """Admin can create a prompt."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        resp = client.post(
            "/api/prompts",
            data=json.dumps({
                "prompt_type": "papa",
                "name": "Test PAPA",
                "prompt_text": "Process announcements...",
                "description": "Test description",
            }),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Test PAPA"
        assert data["created_by"] == "admin@plmediaagency.com"

    def test_create_as_user_returns_403(self, client, db_session, auth_headers):
        """Non-admin user cannot create a prompt."""
        headers = auth_headers("user@plmediaagency.com", "user")
        resp = client.post(
            "/api/prompts",
            data=json.dumps({
                "prompt_type": "papa",
                "name": "Sneaky",
                "prompt_text": "text",
            }),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 403

    def test_create_missing_fields(self, client, db_session, auth_headers):
        """Missing required fields returns 400."""
        headers = auth_headers("admin2@plmediaagency.com", "admin")
        resp = client.post(
            "/api/prompts",
            data=json.dumps({"prompt_type": "papa"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 400

    def test_create_source_list_with_routing(self, client, db_session, auth_headers):
        """Source list prompt includes routing metadata."""
        headers = auth_headers("admin3@plmediaagency.com", "admin")
        resp = client.post(
            "/api/prompts",
            data=json.dumps({
                "prompt_type": "source-list",
                "name": "IL Local Gov",
                "prompt_text": "Find stories about...",
                "opportunity": "Illinois Local Government News",
                "state": "Illinois",
                "pitches_per_week": 4,
            }),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["opportunity"] == "Illinois Local Government News"
        assert data["pitches_per_week"] == 4


class TestUpdatePrompt:
    """Tests for PUT /api/prompts/:id."""

    def test_update_as_admin(self, client, db_session, auth_headers):
        """Admin can update a prompt."""
        from models.prompt import Prompt

        prompt = Prompt(
            prompt_type="papa", name="Old Name",
            prompt_text="old text", is_active=True,
        )
        db_session.add(prompt)
        db_session.flush()

        headers = auth_headers("updater@plmediaagency.com", "admin")
        resp = client.put(
            f"/api/prompts/{prompt.id}",
            data=json.dumps({"name": "New Name"}),
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "New Name"


class TestDeletePrompt:
    """Tests for DELETE /api/prompts/:id."""

    def test_delete_soft_deletes(self, client, db_session, auth_headers):
        """DELETE sets is_active=False instead of removing row."""
        from models.prompt import Prompt

        prompt = Prompt(
            prompt_type="papa", name="To Delete",
            prompt_text="text", is_active=True,
        )
        db_session.add(prompt)
        db_session.flush()

        headers = auth_headers("deleter@plmediaagency.com", "admin")
        resp = client.delete(
            f"/api/prompts/{prompt.id}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert "deactivated" in resp.get_json()["message"]
