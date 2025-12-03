"""add_document_pairs_and_validation_issues

Revision ID: 7dd6d898c195
Revises: 49a305015151
Create Date: 2025-12-03 00:42:58.709557

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7dd6d898c195'
down_revision: Union[str, None] = '49a305015151'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create document_pairs table
    op.create_table(
        'document_pairs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('po_id', sa.Integer(), nullable=True),
        sa.Column('matching_result_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('current_stage', sa.String(20), nullable=False, server_default='matched'),
        sa.Column('overall_status', sa.String(20), nullable=False, server_default='in_progress'),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('extracted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('matched_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('requires_review', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('has_critical_issues', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
        sa.ForeignKeyConstraint(['po_id'], ['purchase_orders.id'], ),
        sa.ForeignKeyConstraint(['matching_result_id'], ['matching_results.id'], ),
    )
    op.create_index('ix_document_pairs_id', 'document_pairs', ['id'])
    op.create_index('ix_document_pairs_invoice_id', 'document_pairs', ['invoice_id'])
    op.create_index('ix_document_pairs_po_id', 'document_pairs', ['po_id'])
    op.create_index('ix_document_pairs_current_stage', 'document_pairs', ['current_stage'])
    op.create_index('ix_document_pairs_overall_status', 'document_pairs', ['overall_status'])
    op.create_index('ix_document_pairs_requires_review', 'document_pairs', ['requires_review'])
    
    # Create validation_issues table
    op.create_table(
        'validation_issues',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_pair_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('field', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('invoice_value', postgresql.JSONB, nullable=True),
        sa.Column('po_value', postgresql.JSONB, nullable=True),
        sa.Column('suggestion', sa.Text(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolved_by', sa.String(100), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_action', sa.String(50), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['document_pair_id'], ['document_pairs.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_validation_issues_id', 'validation_issues', ['id'])
    op.create_index('ix_validation_issues_document_pair_id', 'validation_issues', ['document_pair_id'])
    op.create_index('ix_validation_issues_severity', 'validation_issues', ['severity'])
    op.create_index('ix_validation_issues_resolved', 'validation_issues', ['resolved'])


def downgrade() -> None:
    op.drop_index('ix_validation_issues_resolved', table_name='validation_issues')
    op.drop_index('ix_validation_issues_severity', table_name='validation_issues')
    op.drop_index('ix_validation_issues_document_pair_id', table_name='validation_issues')
    op.drop_index('ix_validation_issues_id', table_name='validation_issues')
    op.drop_table('validation_issues')
    op.drop_index('ix_document_pairs_requires_review', table_name='document_pairs')
    op.drop_index('ix_document_pairs_overall_status', table_name='document_pairs')
    op.drop_index('ix_document_pairs_current_stage', table_name='document_pairs')
    op.drop_index('ix_document_pairs_po_id', table_name='document_pairs')
    op.drop_index('ix_document_pairs_invoice_id', table_name='document_pairs')
    op.drop_index('ix_document_pairs_id', table_name='document_pairs')
    op.drop_table('document_pairs')

