"""add_contact_email_to_invoices

Revision ID: d7629b2e8f75
Revises: 7dd6d898c195
Create Date: 2025-12-03 02:25:14.593127

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7629b2e8f75'
down_revision: Union[str, None] = '7dd6d898c195'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add contact_email column to invoices table
    op.add_column('invoices', sa.Column('contact_email', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove contact_email column from invoices table
    op.drop_column('invoices', 'contact_email')

