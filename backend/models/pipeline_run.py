"""
PipelineRun model — Audit log for every Grok API call.

One row per API call in the pipeline. Tracks:
  - Which story and prompt were involved
  - The step type (source-list, refinement, amy-bot)
  - Status (pending, running, completed, failed)
  - Input/output text and timing
  - Error messages if the call failed
"""
from datetime import datetime, timezone

from models import db


class PipelineRun(db.Model):
    """Represents a single Grok API call in the pipeline."""

    __tablename__ = "pipeline_runs"

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey("stories.id"))
    prompt_id = db.Column(db.Integer, db.ForeignKey("prompts.id"))
    step_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="pending")
    input_text = db.Column(db.Text)
    output_text = db.Column(db.Text)
    error_message = db.Column(db.Text)
    duration_ms = db.Column(db.Integer)
    started_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    completed_at = db.Column(db.DateTime)

    def to_dict(self):
        """Serialize pipeline run to dictionary for API responses."""
        return {
            "id": self.id,
            "story_id": self.story_id,
            "prompt_id": self.prompt_id,
            "step_type": self.step_type,
            "status": self.status,
            "input_text": self.input_text,
            "output_text": self.output_text,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def __repr__(self):
        return f"<PipelineRun {self.id} ({self.step_type}: {self.status})>"
