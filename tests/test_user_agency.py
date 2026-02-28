"""
Tests for UserAgency model and permission-based prompt filtering.

Covers: model CRUD, to_dict serialization, user-agency relationship,
        prompt filtering by agency/opportunity permissions.
"""
from models.user import User
from models.user_agency import UserAgency
from models.prompt import Prompt


class TestUserAgencyModel:
    """Tests for UserAgency model basics."""

    def test_create_user_agency(self, db_session):
        """Can create a user_agency record with required fields."""
        user = User(google_id="g-ua1", email="ua1@plmediaagency.com")
        db_session.add(user)
        db_session.flush()

        ua = UserAgency(user_id=user.id, agency="Test Agency")
        db_session.add(ua)
        db_session.flush()

        assert ua.id is not None
        assert ua.user_id == user.id
        assert ua.agency == "Test Agency"
        assert ua.opportunity is None
        assert ua.created_at is not None

    def test_create_with_opportunity(self, db_session):
        """Can create with a specific opportunity scope."""
        user = User(google_id="g-ua2", email="ua2@plmediaagency.com")
        db_session.add(user)
        db_session.flush()

        ua = UserAgency(user_id=user.id, agency="Agency A", opportunity="Michigan")
        db_session.add(ua)
        db_session.flush()

        assert ua.opportunity == "Michigan"

    def test_to_dict(self, db_session):
        """to_dict returns expected keys."""
        user = User(google_id="g-ua3", email="ua3@plmediaagency.com")
        db_session.add(user)
        db_session.flush()

        ua = UserAgency(user_id=user.id, agency="Agency B", opportunity="Ohio")
        db_session.add(ua)
        db_session.flush()

        d = ua.to_dict()
        assert d["agency"] == "Agency B"
        assert d["opportunity"] == "Ohio"
        assert "id" in d
        assert "user_id" in d
        assert "created_at" in d

    def test_user_relationship(self, db_session):
        """User.agencies backref returns related UserAgency records."""
        user = User(google_id="g-ua4", email="ua4@plmediaagency.com")
        db_session.add(user)
        db_session.flush()

        ua1 = UserAgency(user_id=user.id, agency="Agency X")
        ua2 = UserAgency(user_id=user.id, agency="Agency Y", opportunity="Texas")
        db_session.add_all([ua1, ua2])
        db_session.flush()

        assert len(user.agencies) == 2


class TestPromptAgencyField:
    """Tests for the agency field on the Prompt model."""

    def test_prompt_has_agency_field(self, db_session):
        """Prompt model supports the agency column."""
        prompt = Prompt(
            prompt_type="source-list",
            name="Test SL",
            prompt_text="text",
            agency="US Regional News",
            opportunity="Michigan",
        )
        db_session.add(prompt)
        db_session.flush()

        assert prompt.agency == "US Regional News"

    def test_to_dict_includes_agency(self, db_session):
        """Prompt.to_dict() includes agency for all types."""
        prompt = Prompt(
            prompt_type="papa",
            name="Test PAPA",
            prompt_text="text",
            agency="Shared Agency",
        )
        db_session.add(prompt)
        db_session.flush()

        d = prompt.to_dict()
        assert d["agency"] == "Shared Agency"
