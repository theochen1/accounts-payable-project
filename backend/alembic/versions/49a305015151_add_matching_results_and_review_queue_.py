"""add_matching_results_and_review_queue_tables

Revision ID: 49a305015151
Revises: 14af0ea4cb1d
Create Date: 2025-12-02 18:36:58.972830

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '49a305015151'
down_revision: Union[str, None] = '14af0ea4cb1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create matching_results table
    op.create_table(
        'matching_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('po_id', sa.Integer(), nullable=True),
        sa.Column('match_status', sa.String(20), nullable=False),
        sa.Column('confidence_score', sa.Numeric(3, 2), nullable=True),
        sa.Column('issues', postgresql.JSONB, nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('matched_by', sa.String(20), nullable=True),
        sa.Column('matched_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('reviewed_by', sa.String(100), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
        sa.ForeignKeyConstraint(['po_id'], ['purchase_orders.id'], ),
    )
    op.create_index('idx_matching_status', 'matching_results', ['match_status'])
    op.create_index('idx_matching_invoice', 'matching_results', ['invoice_id'])
    
    # Create review_queue table
    op.create_table(
        'review_queue',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('matching_result_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('priority', sa.String(10), nullable=False),
        sa.Column('issue_category', sa.String(50), nullable=False),
        sa.Column('assigned_to', sa.String(100), nullable=True),
        sa.Column('sla_deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['matching_result_id'], ['matching_results.id'], ),
    )
    op.create_index('idx_queue_priority', 'review_queue', ['priority'])
    op.create_index('idx_queue_status', 'review_queue', ['resolved_at'])
    
    # Update invoices table status column to support new statuses
    # Note: PostgreSQL doesn't have ENUM constraints in this schema, so we just ensure the column exists
    # The application will handle status validation
    
    # Update purchase_orders table status column similarly
    pass


def downgrade() -> None:
    op.drop_index('idx_queue_status', table_name='review_queue')
    op.drop_index('idx_queue_priority', table_name='review_queue')
    op.drop_table('review_queue')
    op.drop_index('idx_matching_invoice', table_name='matching_results')
    op.drop_index('idx_matching_status', table_name='matching_results')
    op.drop_table('matching_results')

