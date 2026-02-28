"""
UserAgency model — maps users to agency/opportunity access.

If opportunity is NULL, user has access to ALL opportunities under that agency.
If opportunity is set, user only sees prompts matching that specific opportunity.
Admins bypass all permission checks.
"""
from datetime import datetime, timezone

from models import db


class UserAgency(db.Model):
    """Maps a user to an agency (and optionally a specific opportunity)."""

    __tablename__ = "user_agencies"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    agency = db.Column(db.String(255), nullable=False)
    opportunity = db.Column(db.String(255))
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship("User", backref="agencies")

    def to_dict(self):
        """Serialize to dictionary for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "agency": self.agency,
            "opportunity": self.opportunity,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        opp = f"/{self.opportunity}" if self.opportunity else ""
        return f"<UserAgency user_id={self.user_id} {self.agency}{opp}>"
