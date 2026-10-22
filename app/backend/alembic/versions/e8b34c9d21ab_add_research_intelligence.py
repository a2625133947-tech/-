"""Add independent broker research tables, preserving all existing rows.

Revision ID: e8b34c9d21ab
Revises: d5e78f9a1b2c
"""
from alembic import op
from app.backend.database.models import ResearchCacheRecord, ResearchDocumentRecord, ResearchTaskRecord

revision = "e8b34c9d21ab"
down_revision = "d5e78f9a1b2c"
branch_labels = None
depends_on = None


def upgrade():
    for model in (ResearchDocumentRecord, ResearchCacheRecord, ResearchTaskRecord):
        model.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade():
    for model in (ResearchTaskRecord, ResearchCacheRecord, ResearchDocumentRecord):
        model.__table__.drop(bind=op.get_bind(), checkfirst=True)
