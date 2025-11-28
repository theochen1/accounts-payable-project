from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID


class AgentTaskResponse(BaseModel):
    """Response schema for agent task"""
    task_id: str
    invoice_id: int
    task_type: str
    status: str
    confidence_score: Optional[float] = None
    reasoning: Optional[str] = None
    resolution_action: Optional[str] = None
    applied: bool
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    output_data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class AgentTaskCreate(BaseModel):
    """Request schema for creating agent task"""
    invoice_id: int
    task_type: str

