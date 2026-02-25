"""
Tests for routes/stories.py — story listing, detail, stats.
"""
from models.story import Story


class TestListStories:
    """Tests for GET /api/stories."""

    def test_list_requires_auth(self, client, db_session):
        """GET /stories without token returns 401."""
        resp = client.get("/api/stories")
        assert resp.status_code == 401

    def test_list_empty(self, client, db_session, auth_headers):
        """GET /stories with no data returns empty list."""
        headers = auth_headers("stories@plmediaagency.com", "user")
        resp = client.get("/api/stories", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["stories"] == []
        assert data["total"] == 0

    def test_list_with_decision_filter(self, client, db_session, auth_headers):
        """GET /stories?decision=APPROVE filters correctly."""
        db_session.add(Story(validation_decision="APPROVE", is_valid=True))
        db_session.add(Story(validation_decision="REJECT", is_valid=False))
        db_session.flush()

        headers = auth_headers("stories2@plmediaagency.com", "user")
        resp = client.get("/api/stories?decision=APPROVE", headers=headers)
        data = resp.get_json()
        assert data["total"] == 1
        assert data["stories"][0]["validation_decision"] == "APPROVE"


class TestGetStory:
    """Tests for GET /api/stories/:id."""

    def test_get_not_found(self, client, db_session, auth_headers):
        """GET /stories/9999 returns 404."""
        headers = auth_headers("detail@plmediaagency.com", "user")
        resp = client.get("/api/stories/9999", headers=headers)
        assert resp.status_code == 404

    def test_get_story_with_runs(self, client, db_session, auth_headers):
        """GET /stories/:id includes pipeline_runs."""
        story = Story(validation_decision="APPROVE", is_valid=True)
        db_session.add(story)
        db_session.flush()

        headers = auth_headers("detail2@plmediaagency.com", "user")
        resp = client.get(f"/api/stories/{story.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "pipeline_runs" in data


class TestStoryStats:
    """Tests for GET /api/stories/stats."""

    def test_stats_empty(self, client, db_session, auth_headers):
        """Stats with no stories returns zeros."""
        headers = auth_headers("stats@plmediaagency.com", "user")
        resp = client.get("/api/stories/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 0
        assert data["approval_rate"] == 0

    def test_stats_with_data(self, client, db_session, auth_headers):
        """Stats correctly calculates approval rate."""
        db_session.add(Story(
            validation_decision="APPROVE", is_valid=True,
            opportunity="IL News",
        ))
        db_session.add(Story(
            validation_decision="REJECT", is_valid=False,
            opportunity="IL News",
        ))
        db_session.add(Story(
            validation_decision="APPROVE", is_valid=True,
            opportunity="Kin",
        ))
        db_session.flush()

        headers = auth_headers("stats2@plmediaagency.com", "user")
        resp = client.get("/api/stories/stats", headers=headers)
        data = resp.get_json()
        assert data["total"] == 3
        assert data["approved"] == 2
        assert data["rejected"] == 1
        assert data["approval_rate"] == 66.7
