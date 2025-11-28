"""Add agent tables

Revision ID: 003_agents
Revises: 002_documents
Create Date: 2024-11-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_agents'
down_revision: Union[str, None] = '002_documents'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create agent_tasks table
    op.create_table(
        'agent_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('task_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        
        # Input/Output
        sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('output_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        
        # Agent execution
        sa.Column('agent_name', sa.String(100), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('tools_used', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        
        # Resolution
        sa.Column('resolution_action', sa.String(50), nullable=True),
        sa.Column('applied', sa.Boolean(), nullable=False, server_default='false'),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_agent_tasks_invoice', 'agent_tasks', ['invoice_id'])
    op.create_index('idx_agent_tasks_status', 'agent_tasks', ['status'])
    
    # Create agent_task_steps table
    op.create_table(
        'agent_task_steps',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_name', sa.String(100), nullable=False),
        sa.Column('step_type', sa.String(50), nullable=True),
        sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('output_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        
        sa.ForeignKeyConstraint(['task_id'], ['agent_tasks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_agent_task_steps_task', 'agent_task_steps', ['task_id'])


def downgrade() -> None:
    op.drop_index('idx_agent_task_steps_task', table_name='agent_task_steps')
    op.drop_table('agent_task_steps')
    op.drop_index('idx_agent_tasks_status', table_name='agent_tasks')
    op.drop_index('idx_agent_tasks_invoice', table_name='agent_tasks')
    op.drop_table('agent_tasks')

