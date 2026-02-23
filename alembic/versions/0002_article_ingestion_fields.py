"""Add article ingestion fields: is_partial, author, lead_image_url, body_html

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-23

Hand-written migration — adds columns required by the ingestion pipeline.
The is_partial column uses server_default so existing rows get false without
a full table rewrite.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("author", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("lead_image_url", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("body_html", sa.Text(), nullable=True))
    op.add_column(
        "articles",
        sa.Column(
            "is_partial",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("articles", "is_partial")
    op.drop_column("articles", "body_html")
    op.drop_column("articles", "lead_image_url")
    op.drop_column("articles", "author")
