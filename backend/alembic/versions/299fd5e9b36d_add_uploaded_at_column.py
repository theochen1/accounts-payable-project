"""add_uploaded_at_column

Revision ID: 299fd5e9b36d
Revises: 03ae58a60df2
Create Date: 2025-12-02 01:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '299fd5e9b36d'
down_revision: Union[str, None] = '03ae58a60df2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add uploaded_at column if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='documents' AND column_name='uploaded_at') THEN
                ALTER TABLE documents ADD COLUMN uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT now();
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Remove uploaded_at column if it exists
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name='documents' AND column_name='uploaded_at') THEN
                ALTER TABLE documents DROP COLUMN uploaded_at;
            END IF;
        END $$;
    """)
