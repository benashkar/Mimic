"""
Tests for routes/queue.py — Queue CRUD, permission filtering, execute flow.

Covers: list (filtered), claim, discard, execute, stats, edge cases.
"""
from unittest.mock import patch, MagicMock

from models import db
from models.prompt import Prompt
from models.story import Story
from models.pipeline_run import PipelineRun
from models.queue_item import QueueItem
from models.user_agency import UserAgency


def _make_prompt_and_story(db_session, agency="Agency A", opportunity="Michigan", state="MI"):
    """Helper to create a prompt and story for queue item tests."""
    prompt = Prompt(
        prompt_type="source-list", name="Test SL", prompt_text="t",
        agency=agency, opportunity=opportunity, state=state,
        is_active=True, created_by="test",
    )
    db_session.add(prompt)
    db_session.flush()

    story = Story(
        source_list_prompt_id=prompt.id,
        opportunity=opportunity, state=state,
        created_by="scheduler",
    )
    db_session.add(story)
    db_session.flush()
    return prompt, story


def _make_queue_item(db_session, story, prompt, label="Source 1", body="Content here",
                     agency="Agency A", opportunity="Michigan", state="MI", status="pending"):
    """Helper to create a queue item."""
    item = QueueItem(
        story_id=story.id, prompt_id=prompt.id,
        label=label, body=body,
        agency=agency, opportunity=opportunity, state=state,
        status=status,
    )
    db_session.add(item)
    db_session.flush()
    return item


class TestListQueue:
    """Tests for GET /api/queue."""

    def test_list_pending_items(self, client, auth_headers, db_session):
        """Admin sees all pending queue items."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        prompt, story = _make_prompt_and_story(db_session)
        _make_queue_item(db_session, story, prompt)
        _make_queue_item(db_session, story, prompt, label="Source 2", body="More content")
        db_session.commit()

        resp = client.get("/api/queue", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 2

    def test_filter_by_status(self, client, auth_headers, db_session):
        """Can filter by status query param."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        prompt, story = _make_prompt_and_story(db_session)
        _make_queue_item(db_session, story, prompt, status="pending")
        _make_queue_item(db_session, story, prompt, label="Done", body="done", status="completed")
        db_session.commit()

        resp = client.get("/api/queue?status=completed", headers=headers)
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["label"] == "Done"

    def test_permission_filtering_non_admin(self, client, make_user, db_session, app):
        """Non-admin user only sees items matching their agency assignments."""
        from services.auth_service import generate_jwt

        user = make_user(email="q1@plmediaagency.com", role="user", google_id="gq1")
        ua = UserAgency(user_id=user.id, agency="Agency A")
        db_session.add(ua)

        prompt_a, story_a = _make_prompt_and_story(db_session, agency="Agency A")
        prompt_b, story_b = _make_prompt_and_story(db_session, agency="Agency B", opportunity="Ohio")
        _make_queue_item(db_session, story_a, prompt_a, agency="Agency A")
        _make_queue_item(db_session, story_b, prompt_b, agency="Agency B", opportunity="Ohio")
        db_session.commit()

        with app.app_context():
            token = generate_jwt(user)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/queue", headers=headers)
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["agency"] == "Agency A"

    def test_requires_auth(self, client):
        """GET without auth returns 401."""
        resp = client.get("/api/queue")
        assert resp.status_code == 401


class TestClaimItems:
    """Tests for POST /api/queue/claim."""

    def test_claim_pending_items(self, client, auth_headers, db_session):
        """Claim marks items as claimed with user email and timestamp."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        prompt, story = _make_prompt_and_story(db_session)
        item = _make_queue_item(db_session, story, prompt)
        db_session.commit()

        resp = client.post("/api/queue/claim", json={"item_ids": [item.id]}, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert item.id in data["claimed"]

        db_session.expire_all()
        updated = db_session.get(QueueItem, item.id)
        assert updated.status == "claimed"
        assert updated.claimed_by == "admin@plmediaagency.com"
        assert updated.claimed_at is not None

    def test_skip_non_pending(self, client, auth_headers, db_session):
        """Already-claimed items are skipped."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        prompt, story = _make_prompt_and_story(db_session)
        item = _make_queue_item(db_session, story, prompt, status="completed")
        db_session.commit()

        resp = client.post("/api/queue/claim", json={"item_ids": [item.id]}, headers=headers)
        data = resp.get_json()
        assert data["claimed"] == []

    def test_missing_item_ids(self, client, auth_headers):
        """POST without item_ids returns 400."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        resp = client.post("/api/queue/claim", json={}, headers=headers)
        assert resp.status_code == 400


class TestDiscardItems:
    """Tests for POST /api/queue/discard."""

    def test_discard_pending_item(self, client, auth_headers, db_session):
        """Discard marks pending items as discarded."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        prompt, story = _make_prompt_and_story(db_session)
        item = _make_queue_item(db_session, story, prompt)
        db_session.commit()

        resp = client.post("/api/queue/discard", json={"item_ids": [item.id]}, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert item.id in data["discarded"]

        db_session.expire_all()
        updated = db_session.get(QueueItem, item.id)
        assert updated.status == "discarded"

    def test_discard_claimed_item(self, client, auth_headers, db_session):
        """Claimed items can also be discarded."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        prompt, story = _make_prompt_and_story(db_session)
        item = _make_queue_item(db_session, story, prompt, status="claimed")
        db_session.commit()

        resp = client.post("/api/queue/discard", json={"item_ids": [item.id]}, headers=headers)
        data = resp.get_json()
        assert item.id in data["discarded"]

    def test_skip_completed_item(self, client, auth_headers, db_session):
        """Completed items cannot be discarded."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        prompt, story = _make_prompt_and_story(db_session)
        item = _make_queue_item(db_session, story, prompt, status="completed")
        db_session.commit()

        resp = client.post("/api/queue/discard", json={"item_ids": [item.id]}, headers=headers)
        data = resp.get_json()
        assert data["discarded"] == []


class TestExecuteItem:
    """Tests for POST /api/queue/execute."""

    @patch("routes.queue.threading.Thread")
    def test_execute_returns_202(self, mock_thread, client, auth_headers, db_session):
        """Execute starts pipeline in background thread, returns 202."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        prompt, story = _make_prompt_and_story(db_session)
        item = _make_queue_item(db_session, story, prompt)

        ref_prompt = Prompt(
            prompt_type="papa", name="PAPA", prompt_text="refine", created_by="test"
        )
        db_session.add(ref_prompt)
        db_session.flush()
        db_session.commit()

        mock_thread.return_value = MagicMock()

        resp = client.post("/api/queue/execute", json={
            "item_id": item.id,
            "refinement_prompt_id": ref_prompt.id,
        }, headers=headers)
        assert resp.status_code == 202
        data = resp.get_json()
        assert data["item_id"] == item.id
        assert data["story_id"] == story.id
        assert data["status"] == "running"

        # Verify item is now claimed
        db_session.expire_all()
        updated = db_session.get(QueueItem, item.id)
        assert updated.status == "claimed"

        # Verify placeholder run was created
        run = PipelineRun.query.filter_by(
            story_id=story.id, step_type="refinement", status="running"
        ).first()
        assert run is not None

    def test_missing_fields(self, client, auth_headers):
        """POST without required fields returns 400."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        resp = client.post("/api/queue/execute", json={}, headers=headers)
        assert resp.status_code == 400

    def test_item_not_found(self, client, auth_headers):
        """POST with nonexistent item returns 404."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        resp = client.post("/api/queue/execute", json={
            "item_id": 9999,
            "refinement_prompt_id": 1,
        }, headers=headers)
        assert resp.status_code == 404

    def test_cannot_execute_completed_item(self, client, auth_headers, db_session):
        """Cannot execute an already-completed item."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        prompt, story = _make_prompt_and_story(db_session)
        item = _make_queue_item(db_session, story, prompt, status="completed")
        db_session.commit()

        resp = client.post("/api/queue/execute", json={
            "item_id": item.id,
            "refinement_prompt_id": 1,
        }, headers=headers)
        assert resp.status_code == 400
        assert "status" in resp.get_json()["error"]


class TestQueueStats:
    """Tests for GET /api/queue/stats."""

    def test_returns_counts(self, client, auth_headers, db_session):
        """Stats returns counts for each status."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        prompt, story = _make_prompt_and_story(db_session)
        _make_queue_item(db_session, story, prompt, status="pending")
        _make_queue_item(db_session, story, prompt, label="S2", body="b2", status="pending")
        _make_queue_item(db_session, story, prompt, label="S3", body="b3", status="completed")
        _make_queue_item(db_session, story, prompt, label="S4", body="b4", status="discarded")
        db_session.commit()

        resp = client.get("/api/queue/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["pending"] == 2
        assert data["completed"] == 1
        assert data["discarded"] == 1
        assert data["total"] == 4

    def test_empty_queue(self, client, auth_headers):
        """Stats on empty queue returns all zeros."""
        headers = auth_headers("admin@plmediaagency.com", "admin")
        resp = client.get("/api/queue/stats", headers=headers)
        data = resp.get_json()
        assert data["pending"] == 0
        assert data["total"] == 0

    def test_requires_auth(self, client):
        """GET without auth returns 401."""
        resp = client.get("/api/queue/stats")
        assert resp.status_code == 401
