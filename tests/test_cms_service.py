"""
Tests for services/cms_service.py — CMS push stub.

Currently tests the stub implementation. Will need updating
when real Lumen API integration is added in Phase 8.
"""
from models.story import Story
from services.cms_service import push_to_cms


class TestPushToCms:
    """Tests for push_to_cms stub."""

    def test_returns_stub_response(self, app, db_session):
        """Stub returns dict with status='stub' and story_id."""
        with app.app_context():
            story = Story(created_by="test", opportunity="TestOpp")
            db_session.add(story)
            db_session.flush()

            result = push_to_cms(story)
            assert result["status"] == "stub"
            assert result["story_id"] == story.id

    def test_includes_message(self, app, db_session):
        """Stub response includes descriptive message."""
        with app.app_context():
            story = Story(created_by="test")
            db_session.add(story)
            db_session.flush()

            result = push_to_cms(story)
            assert "pending" in result["message"].lower()

    def test_handles_no_opportunity(self, app, db_session):
        """Stub works when story has no opportunity set."""
        with app.app_context():
            story = Story(created_by="test")
            db_session.add(story)
            db_session.flush()

            result = push_to_cms(story)
            assert result["status"] == "stub"
