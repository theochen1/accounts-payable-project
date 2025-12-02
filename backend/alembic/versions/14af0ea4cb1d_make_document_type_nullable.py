"""make_document_type_nullable

Revision ID: 14af0ea4cb1d
Revises: 299fd5e9b36d
Create Date: 2025-12-02 01:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '14af0ea4cb1d'
down_revision: Union[str, None] = '299fd5e9b36d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make document_type nullable (it's set during classification step)
    op.alter_column('documents', 'document_type', nullable=True)


def downgrade() -> None:
    # Make document_type NOT NULL again (set default for existing nulls)
    op.execute("UPDATE documents SET document_type = 'invoice' WHERE document_type IS NULL")
    op.alter_column('documents', 'document_type', nullable=False)
