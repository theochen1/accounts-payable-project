"""Add documents table and source_document_id columns

Revision ID: 002_documents
Revises: 001_initial
Create Date: 2024-11-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_documents'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create documents table (processing queue)
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('storage_path', sa.String(), nullable=False),
        sa.Column('document_type', sa.String(), nullable=True),  # 'invoice' | 'po' | null
        sa.Column('status', sa.String(), nullable=True, server_default='pending'),  # pending, processing, processed, error
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('ocr_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('processed_id', sa.Integer(), nullable=True),  # ID of created Invoice or PurchaseOrder
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_id'), 'documents', ['id'], unique=False)
    op.create_index(op.f('ix_documents_status'), 'documents', ['status'], unique=False)
    
    # Add source_document_id to invoices
    op.add_column('invoices', sa.Column('source_document_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_invoices_source_document_id',
        'invoices', 'documents',
        ['source_document_id'], ['id']
    )
    
    # Add source_document_id and order_date to purchase_orders
    op.add_column('purchase_orders', sa.Column('source_document_id', sa.Integer(), nullable=True))
    op.add_column('purchase_orders', sa.Column('order_date', sa.Date(), nullable=True))
    op.create_foreign_key(
        'fk_purchase_orders_source_document_id',
        'purchase_orders', 'documents',
        ['source_document_id'], ['id']
    )


def downgrade() -> None:
    # Remove foreign keys and columns from purchase_orders
    op.drop_constraint('fk_purchase_orders_source_document_id', 'purchase_orders', type_='foreignkey')
    op.drop_column('purchase_orders', 'source_document_id')
    op.drop_column('purchase_orders', 'order_date')
    
    # Remove foreign key and column from invoices
    op.drop_constraint('fk_invoices_source_document_id', 'invoices', type_='foreignkey')
    op.drop_column('invoices', 'source_document_id')
    
    # Drop documents table
    op.drop_index(op.f('ix_documents_status'), table_name='documents')
    op.drop_index(op.f('ix_documents_id'), table_name='documents')
    op.drop_table('documents')

