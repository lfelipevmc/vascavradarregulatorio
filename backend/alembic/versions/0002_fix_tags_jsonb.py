"""fix tags and setores_interesse from ARRAY to JSONB

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert tags: VARCHAR[] -> JSONB (existing NULL values stay NULL)
    op.execute("""
        ALTER TABLE normativos
        ALTER COLUMN tags TYPE JSONB
        USING CASE
            WHEN tags IS NULL THEN NULL
            ELSE to_jsonb(tags)
        END
    """)

    # Convert setores_interesse: VARCHAR[] -> JSONB
    op.execute("""
        ALTER TABLE usuarios
        ALTER COLUMN setores_interesse TYPE JSONB
        USING CASE
            WHEN setores_interesse IS NULL THEN NULL
            ELSE to_jsonb(setores_interesse)
        END
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE normativos
        ALTER COLUMN tags TYPE VARCHAR[]
        USING CASE
            WHEN tags IS NULL THEN NULL
            ELSE ARRAY(SELECT jsonb_array_elements_text(tags))
        END
    """)

    op.execute("""
        ALTER TABLE usuarios
        ALTER COLUMN setores_interesse TYPE VARCHAR[]
        USING CASE
            WHEN setores_interesse IS NULL THEN NULL
            ELSE ARRAY(SELECT jsonb_array_elements_text(setores_interesse))
        END
    """)
