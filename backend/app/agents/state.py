from typing import TypedDict, List, Optional, Literal
from decimal import Decimal


class AgentState(TypedDict):
    """State passed between agent nodes."""
    
    # Input context
    invoice_id: str
    invoice_data: dict
    po_data: dict
    matching_result: dict
    exception_type: str  # 'vendor_mismatch', 'price_variance', etc.
    
    # Agent workflow state
    current_step: str
    confidence_score: float
    reasoning: str
    tools_used: List[dict]
    
    # Resolution state
    resolution_action: Optional[str]  # 'update_vendor', 'override_price', etc.
    resolution_data: Optional[dict]
    should_escalate: bool
    escalation_reason: Optional[str]
    
    # Metadata
    iteration_count: int

