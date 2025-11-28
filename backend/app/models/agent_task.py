from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class AgentTask(Base):
    """Represents an AI agent task for resolving invoice matching exceptions"""
    __tablename__ = "agent_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    task_type = Column(String(50), nullable=False)  # 'vendor_mismatch', 'price_variance', etc.
    status = Column(String(20), nullable=False, default="pending", index=True)  # 'pending', 'running', 'completed', 'failed', 'escalated'
    confidence_score = Column(Float, nullable=True)
    
    # Input/Output
    input_data = Column(JSONB, nullable=False)
    output_data = Column(JSONB, nullable=True)
    
    # Agent execution
    agent_name = Column(String(100), nullable=True)
    reasoning = Column(Text, nullable=True)
    tools_used = Column(JSONB, nullable=True)
    
    # Resolution
    resolution_action = Column(String(50), nullable=True)  # 'auto_fixed', 'escalated', 'failed'
    applied = Column(Boolean, nullable=False, default=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    invoice = relationship("Invoice", backref="agent_tasks")
    steps = relationship("AgentTaskStep", back_populates="task", cascade="all, delete-orphan")


class AgentTaskStep(Base):
    """Represents a single step in an agent task execution"""
    __tablename__ = "agent_task_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("agent_tasks.id"), nullable=False, index=True)
    step_name = Column(String(100), nullable=False)
    step_type = Column(String(50), nullable=True)  # 'tool_call', 'llm_response', 'decision'
    input_data = Column(JSONB, nullable=True)
    output_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    task = relationship("AgentTask", back_populates="steps")

