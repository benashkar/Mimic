"""
Prompt model — The Prompt Library.

Three prompt_type values:
  'source-list' — Discovery prompts with routing metadata (issuer, opportunity, etc.)
  'papa'        — PAPA and PSST refinement prompts (distinguished by name)
  'amy-bot'     — Editorial validation prompts

Source List prompts carry routing metadata (nullable columns).
PAPA/PSST/Amy Bot prompts only use the common fields.
"""
from datetime import datetime, timezone

from models import db


class Prompt(db.Model):
    """Represents a prompt configuration in the Prompt Library."""

    __tablename__ = "prompts"

    id = db.Column(db.Integer, primary_key=True)
    prompt_type = db.Column(db.String(50), nullable=False)

    # Common fields (all types)
    name = db.Column(db.String(255), nullable=False)
    prompt_text = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.String(255))
    updated_by = db.Column(db.String(255))
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Source List routing metadata (nullable — only for source-list type)
    issuer = db.Column(db.String(255))
    opportunity = db.Column(db.String(255))
    state = db.Column(db.String(255))
    publications = db.Column(db.Text)
    topic_summary = db.Column(db.Text)
    context = db.Column(db.Text)
    pitches_per_week = db.Column(db.Integer)

    # Relationships — stories that reference this prompt
    stories_as_source = db.relationship(
        "Story", foreign_keys="Story.source_list_prompt_id", backref="source_list_prompt", lazy=True
    )
    stories_as_refinement = db.relationship(
        "Story", foreign_keys="Story.refinement_prompt_id", backref="refinement_prompt", lazy=True
    )
    stories_as_amy_bot = db.relationship(
        "Story", foreign_keys="Story.amy_bot_prompt_id", backref="amy_bot_prompt", lazy=True
    )
    pipeline_runs = db.relationship("PipelineRun", backref="prompt", lazy=True)

    def to_dict(self):
        """Serialize prompt to dictionary for API responses."""
        result = {
            "id": self.id,
            "prompt_type": self.prompt_type,
            "name": self.name,
            "prompt_text": self.prompt_text,
            "description": self.description,
            "is_active": self.is_active,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        # Include routing metadata only for source-list prompts
        if self.prompt_type == "source-list":
            result.update({
                "issuer": self.issuer,
                "opportunity": self.opportunity,
                "state": self.state,
                "publications": self.publications,
                "topic_summary": self.topic_summary,
                "context": self.context,
                "pitches_per_week": self.pitches_per_week,
            })
        return result

    def __repr__(self):
        return f"<Prompt {self.name} ({self.prompt_type})>"
