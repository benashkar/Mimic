"""
Story model — Every pipeline run result (approved AND rejected).

A story tracks the full pipeline journey:
  1. Source List discovery (input/output/selection)
  2. Routing metadata snapshot (copied from source list config at runtime)
  3. PAPA or PSST refinement (input/output)
  4. Amy Bot validation (input/output/decision)
  5. CMS push (only if APPROVE)

Rejected stories are logged but no CMS push happens. Story is dead.
"""
from datetime import datetime, timezone

from models import db


class Story(db.Model):
    """Represents a story produced by the pipeline."""

    __tablename__ = "stories"

    id = db.Column(db.Integer, primary_key=True)

    # Which prompts were used (FK refs to prompts table)
    source_list_prompt_id = db.Column(
        db.Integer, db.ForeignKey("prompts.id")
    )
    refinement_prompt_id = db.Column(
        db.Integer, db.ForeignKey("prompts.id")
    )
    amy_bot_prompt_id = db.Column(
        db.Integer, db.ForeignKey("prompts.id")
    )

    # Step 1: Source List
    source_list_input = db.Column(db.Text)
    source_list_output = db.Column(db.Text)
    selected_story = db.Column(db.Text)
    url_enrichments = db.Column(db.Text)

    # Routing snapshot (copied from source list config at runtime)
    opportunity = db.Column(db.String(255))
    state = db.Column(db.String(255))
    publications = db.Column(db.Text)
    topic_summary = db.Column(db.Text)
    context = db.Column(db.Text)

    # Step 3: PAPA or PSST output
    refinement_input = db.Column(db.Text)
    refinement_output = db.Column(db.Text)

    # Step 4: Amy Bot output
    amy_bot_input = db.Column(db.Text)
    amy_bot_output = db.Column(db.Text)
    is_valid = db.Column(db.Boolean, default=False)
    validation_decision = db.Column(db.String(20))

    # CMS push (only if APPROVE)
    pushed_to_cms = db.Column(db.Boolean, default=False)
    cms_push_date = db.Column(db.DateTime)
    cms_response = db.Column(db.Text)

    # Audit
    created_by = db.Column(db.String(255))
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship to pipeline_runs
    pipeline_runs = db.relationship("PipelineRun", backref="story", lazy=True)

    def to_dict(self):
        """Serialize story to dictionary for API responses."""
        return {
            "id": self.id,
            "source_list_prompt_id": self.source_list_prompt_id,
            "refinement_prompt_id": self.refinement_prompt_id,
            "amy_bot_prompt_id": self.amy_bot_prompt_id,
            "source_list_input": self.source_list_input,
            "source_list_output": self.source_list_output,
            "selected_story": self.selected_story,
            "url_enrichments": self.url_enrichments,
            "opportunity": self.opportunity,
            "state": self.state,
            "publications": self.publications,
            "topic_summary": self.topic_summary,
            "context": self.context,
            "refinement_input": self.refinement_input,
            "refinement_output": self.refinement_output,
            "amy_bot_input": self.amy_bot_input,
            "amy_bot_output": self.amy_bot_output,
            "is_valid": self.is_valid,
            "validation_decision": self.validation_decision,
            "pushed_to_cms": self.pushed_to_cms,
            "cms_push_date": self.cms_push_date.isoformat() if self.cms_push_date else None,
            "cms_response": self.cms_response,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Story {self.id} ({self.validation_decision or 'pending'})>"
