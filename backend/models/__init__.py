"""
SQLAlchemy database instance and model imports.

All models are imported here so that `from models import db` gives access
to the shared db instance, and `from models import User, Prompt, ...`
gives access to all model classes.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import all models so they register with SQLAlchemy metadata
from models.user import User  # noqa: E402, F401
from models.prompt import Prompt  # noqa: E402, F401
from models.story import Story  # noqa: E402, F401
from models.pipeline_run import PipelineRun  # noqa: E402, F401
