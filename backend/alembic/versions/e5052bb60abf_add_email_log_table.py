"""add_email_log_table

Revision ID: e5052bb60abf
Revises: d7629b2e8f75
Create Date: 2025-12-03 08:49:54.370337

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5052bb60abf'
down_revision: Union[str, None] = 'd7629b2e8f75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create email_log table
    op.create_table(
        'email_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_pair_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('to_addresses', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('cc_addresses', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('subject', sa.String(), nullable=False),
        sa.Column('body_text', sa.Text(), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=True),
        sa.Column('issue_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='draft'),
        sa.Column('gmail_message_id', sa.String(), nullable=True),
        sa.Column('gmail_thread_id', sa.String(), nullable=True),
        sa.Column('drafted_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('drafted_by', sa.String(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_by', sa.String(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['document_pair_id'], ['document_pairs.id'], ondelete='CASCADE'),
    )
    
    # Create indexes
    op.create_index('idx_email_log_pair', 'email_log', ['document_pair_id'])
    op.create_index('idx_email_log_status', 'email_log', ['status'])


def downgrade() -> None:
    op.drop_index('idx_email_log_status', table_name='email_log')
    op.drop_index('idx_email_log_pair', table_name='email_log')
    op.drop_table('email_log')

