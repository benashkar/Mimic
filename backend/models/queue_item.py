"""
QueueItem model — Pending sources discovered by the scheduler.

Each row represents a single parsed source from a scheduled source list run.
Status workflow: pending → claimed → completed / failed / discarded

Users see pending items filtered by their UserAgency permissions,
pick PAPA/PSST, and execute the pipeline from the queue page.
"""
from datetime import datetime, timezone

from models import db


class QueueItem(db.Model):
    """Represents a queued source awaiting human review and refinement."""

    __tablename__ = "queue_items"

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey("stories.id"), nullable=False)
    prompt_id = db.Column(db.Integer, db.ForeignKey("prompts.id"), nullable=False)
    label = db.Column(db.Text, nullable=False)
    body = db.Column(db.Text, nullable=False)
    agency = db.Column(db.String(255))
    opportunity = db.Column(db.String(255))
    state = db.Column(db.String(255))
    status = db.Column(db.String(50), nullable=False, default="pending")
    claimed_by = db.Column(db.String(255))
    claimed_at = db.Column(db.DateTime)
    refinement_prompt_id = db.Column(
        db.Integer, db.ForeignKey("prompts.id")
    )
    pipeline_story_id = db.Column(
        db.Integer, db.ForeignKey("stories.id")
    )
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    story = db.relationship(
        "Story", foreign_keys=[story_id], backref="queue_items"
    )
    prompt = db.relationship(
        "Prompt", foreign_keys=[prompt_id], backref="queue_items"
    )
    refinement_prompt = db.relationship(
        "Prompt", foreign_keys=[refinement_prompt_id]
    )
    pipeline_story = db.relationship(
        "Story", foreign_keys=[pipeline_story_id]
    )

    def to_dict(self):
        """Serialize queue item to dictionary for API responses."""
        return {
            "id": self.id,
            "story_id": self.story_id,
            "prompt_id": self.prompt_id,
            "label": self.label,
            "body": self.body,
            "agency": self.agency,
            "opportunity": self.opportunity,
            "state": self.state,
            "status": self.status,
            "claimed_by": self.claimed_by,
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "refinement_prompt_id": self.refinement_prompt_id,
            "pipeline_story_id": self.pipeline_story_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<QueueItem {self.id} ({self.status})>"
