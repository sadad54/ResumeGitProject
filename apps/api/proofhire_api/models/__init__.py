"""SQLAlchemy models, one module per aggregate.

Import every model module here so Base.metadata is complete for Alembic
autogenerate (apps/api/alembic/env.py imports this package).
"""

from proofhire_api.models.evidence import Evidence, EvidenceSkill, EvidenceSource  # noqa: F401
from proofhire_api.models.github_connection import GitHubConnection  # noqa: F401
from proofhire_api.models.job import Job  # noqa: F401
from proofhire_api.models.repository import Repository  # noqa: F401
from proofhire_api.models.requirement import Requirement  # noqa: F401
from proofhire_api.models.skill import Skill  # noqa: F401
from proofhire_api.models.source_artifact import SourceArtifact  # noqa: F401
from proofhire_api.models.sync_run import SyncRun  # noqa: F401
from proofhire_api.models.user import User  # noqa: F401
