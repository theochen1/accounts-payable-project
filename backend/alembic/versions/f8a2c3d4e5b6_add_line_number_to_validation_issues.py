"""add line_number to validation_issues

Revision ID: f8a2c3d4e5b6
Revises: e5052bb60abf
Create Date: 2024-12-03 15:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8a2c3d4e5b6'
down_revision = 'e5052bb60abf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add line_number column to validation_issues table
    op.add_column('validation_issues', sa.Column('line_number', sa.Integer(), nullable=True))


def downgrade() -> None:
    # Remove line_number column from validation_issues table
    op.drop_column('validation_issues', 'line_number')

