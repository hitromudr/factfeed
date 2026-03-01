"""Add unique constraint on (article_id, position) to sentences table

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-24

Hand-written migration — prevents duplicate sentence rows when an article
is re-classified. The application uses delete-then-insert, but the DB
constraint provides a safety net.
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_sentences_article_position", "sentences", ["article_id", "position"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_sentences_article_position", "sentences", type_="unique")
