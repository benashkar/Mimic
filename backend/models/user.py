"""
User model — Google OAuth accounts.

Only @plmediaagency.com emails are allowed.
role is either 'admin' or 'user'. First user created becomes admin.
"""
from datetime import datetime, timezone

from models import db


class User(db.Model):
    """Represents an authenticated user from Google OAuth."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    display_name = db.Column(db.String(255))
    avatar_url = db.Column(db.Text)
    role = db.Column(db.String(20), nullable=False, default="user")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    last_login_at = db.Column(db.DateTime)

    def to_dict(self):
        """Serialize user to dictionary for API responses."""
        return {
            "id": self.id,
            "google_id": self.google_id,
            "email": self.email,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
