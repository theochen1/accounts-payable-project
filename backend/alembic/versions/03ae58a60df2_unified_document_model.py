"""unified_document_model

Revision ID: 03ae58a60df2
Revises: 003_agents
Create Date: 2025-12-02 01:30:49.249879

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '03ae58a60df2'
down_revision: Union[str, None] = '003_agents'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Migrate storage_path to file_path if it exists
    # Check if storage_path column exists and migrate data
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name='documents' AND column_name='storage_path') THEN
                ALTER TABLE documents RENAME COLUMN storage_path TO file_path;
            END IF;
        END $$;
    """)
    
    # Drop old documents table columns if they exist
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name='documents' AND column_name='processed_id') THEN
                ALTER TABLE documents DROP COLUMN processed_id;
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name='documents' AND column_name='ocr_data') THEN
                ALTER TABLE documents DROP COLUMN ocr_data;
            END IF;
        END $$;
    """)
    
    # Ensure file_path exists (should exist after rename, but add if missing)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='documents' AND column_name='file_path') THEN
                ALTER TABLE documents ADD COLUMN file_path VARCHAR NOT NULL DEFAULT '';
            END IF;
        END $$;
    """)
    op.add_column('documents', sa.Column('vendor_name', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('document_number', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('document_date', sa.Date(), nullable=True))
    op.add_column('documents', sa.Column('total_amount', sa.Numeric(12, 2), nullable=True))
    op.add_column('documents', sa.Column('currency', sa.String(), nullable=True, server_default='USD'))
    op.add_column('documents', sa.Column('type_specific_data', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('documents', sa.Column('line_items', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('documents', sa.Column('raw_ocr', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('documents', sa.Column('extraction_source', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('vendor_id', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('vendor_match', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('documents', sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True))
    
    # Update document_type to be NOT NULL (will need to handle existing nulls)
    op.execute("UPDATE documents SET document_type = 'invoice' WHERE document_type IS NULL")
    op.alter_column('documents', 'document_type', nullable=False)
    
    # Update status default
    op.alter_column('documents', 'status', server_default='uploaded')
    
    # Create indexes
    op.create_index(op.f('ix_documents_document_type'), 'documents', ['document_type'], unique=False)
    op.create_index(op.f('ix_documents_document_number'), 'documents', ['document_number'], unique=False)
    op.create_index(op.f('ix_documents_vendor_id'), 'documents', ['vendor_id'], unique=False)
    
    # Add foreign key for vendor_id
    op.create_foreign_key(
        'fk_documents_vendor_id',
        'documents', 'vendors',
        ['vendor_id'], ['id']
    )


def downgrade() -> None:
    # Drop foreign key and indexes
    op.drop_constraint('fk_documents_vendor_id', 'documents', type_='foreignkey')
    op.drop_index(op.f('ix_documents_vendor_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_document_number'), table_name='documents')
    op.drop_index(op.f('ix_documents_document_type'), table_name='documents')
    
    # Remove new columns
    op.drop_column('documents', 'processed_at')
    op.drop_column('documents', 'vendor_match')
    op.drop_column('documents', 'vendor_id')
    op.drop_column('documents', 'extraction_source')
    op.drop_column('documents', 'raw_ocr')
    op.drop_column('documents', 'line_items')
    op.drop_column('documents', 'type_specific_data')
    op.drop_column('documents', 'currency')
    op.drop_column('documents', 'total_amount')
    op.drop_column('documents', 'document_date')
    op.drop_column('documents', 'document_number')
    op.drop_column('documents', 'vendor_name')
    op.drop_column('documents', 'file_path')
    
    # Restore old columns
    op.add_column('documents', sa.Column('storage_path', sa.String(), nullable=False, server_default=''))
    op.add_column('documents', sa.Column('ocr_data', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('documents', sa.Column('processed_id', sa.Integer(), nullable=True))
    
    # Restore status default
    op.alter_column('documents', 'status', server_default='pending')
    op.alter_column('documents', 'document_type', nullable=True)
