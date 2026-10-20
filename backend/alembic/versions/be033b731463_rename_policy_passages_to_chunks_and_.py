"""rename policy passages to chunks and add pgvector columns

Revision ID: be033b731463
Revises: 3a8cff904d6a
Create Date: 2026-10-20 11:45:10.381023

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'be033b731463'
down_revision: Union[str, Sequence[str], None] = '3a8cff904d6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions")
    op.rename_table("policy_passages", "policy_chunks")
    op.execute(
        "ALTER TABLE policy_chunks "
        "RENAME CONSTRAINT ck_policy_passages_language TO ck_policy_chunks_language"
    )
    op.add_column("policy_chunks", sa.Column("section_title", sa.String(), nullable=False))
    op.add_column("policy_chunks", sa.Column("content_hash", sa.String(), nullable=False))
    op.add_column("policy_chunks", sa.Column("embedding", Vector(1024), nullable=False))
    op.create_unique_constraint(
        "uq_policy_chunks_section",
        "policy_chunks",
        ["document_name", "language", "section_title"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_policy_chunks_section", "policy_chunks", type_="unique")
    op.drop_column("policy_chunks", "embedding")
    op.drop_column("policy_chunks", "content_hash")
    op.drop_column("policy_chunks", "section_title")
    op.execute(
        "ALTER TABLE policy_chunks "
        "RENAME CONSTRAINT ck_policy_chunks_language TO ck_policy_passages_language"
    )
    op.rename_table("policy_chunks", "policy_passages")