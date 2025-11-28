"""
LangGraph workflow orchestrator for agent-based invoice exception resolution.
"""
import logging
from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from app.config import settings
from app.agents.state import AgentState
from app.agents.nodes import (
    create_analyze_node,
    create_vendor_correction_node,
    create_price_variance_node,
    escalation_node,
    finalize_node
)

logger = logging.getLogger(__name__)


def create_agent_workflow(db_connection_string: str, db: Session = None):
    """
    Create the main agent workflow graph.
    
    Args:
        db_connection_string: PostgreSQL connection string for checkpointer
        db: Database session for nodes (optional, will be passed through state if not provided)
    """
    # Initialize graph
    workflow = StateGraph(AgentState)
    
    # Create nodes with db access
    # For MVP, we'll pass db through state if not provided
    if db:
        analyze_node = create_analyze_node(db)
        vendor_node = create_vendor_correction_node(db)
        price_node = create_price_variance_node(db)
    else:
        # Fallback: nodes will get db from state
        from app.agents.nodes import analyze_exception_node, vendor_correction_node, price_variance_node
        analyze_node = analyze_exception_node
        vendor_node = vendor_correction_node
        price_node = price_variance_node
    
    # Add nodes
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("fix_vendor", vendor_node)
    workflow.add_node("fix_price", price_node)
    workflow.add_node("escalate", escalation_node)
    workflow.add_node("finalize", finalize_node)
    
    # Set entry point
    workflow.set_entry_point("analyze")
    
    # Define routing logic
    workflow.add_conditional_edges(
        "analyze",
        route_by_exception_type,
        {
            "vendor_mismatch": "fix_vendor",
            "price_variance": "fix_price",
            "total_mismatch": "fix_price",  # Total mismatch is a price variance
            "currency_mismatch": "escalate",  # No auto-fix for currency
            "unknown": "escalate"
        }
    )
    
    workflow.add_conditional_edges(
        "fix_vendor",
        check_if_resolved,
        {
            "resolved": "finalize",
            "escalate": "escalate"
        }
    )
    
    workflow.add_conditional_edges(
        "fix_price",
        check_if_resolved,
        {
            "resolved": "finalize",
            "escalate": "escalate"
        }
    )
    
    workflow.add_edge("escalate", END)
    workflow.add_edge("finalize", END)
    
    # Compile with PostgreSQL checkpointer (for state persistence)
    try:
        checkpointer = PostgresSaver.from_conn_string(db_connection_string)
        app = workflow.compile(checkpointer=checkpointer)
        logger.info("Agent workflow compiled successfully with PostgreSQL checkpointer")
    except Exception as e:
        logger.warning(f"Failed to initialize PostgreSQL checkpointer: {e}. Using in-memory checkpointer.")
        # Fallback to in-memory checkpointer for development
        app = workflow.compile()
    
    return app


# Routing functions

def route_by_exception_type(state: AgentState) -> str:
    """Determine which node to route to based on exception type."""
    exception_type = state.get("exception_type", "unknown")
    
    exception_map = {
        "vendor_mismatch": "vendor_mismatch",
        "total_mismatch": "price_variance",
        "currency_mismatch": "currency_mismatch"
    }
    
    # Check matching result issues for exception type
    matching_result = state.get("matching_result", {})
    issues = matching_result.get("issues", [])
    
    if issues:
        first_issue_type = issues[0].get("type", "")
        if first_issue_type in exception_map:
            return exception_map[first_issue_type]
    
    # Fallback to state exception_type
    return exception_map.get(exception_type, "unknown")


def check_if_resolved(state: AgentState) -> str:
    """Check if exception was resolved or needs escalation."""
    if state.get("should_escalate", False):
        return "escalate"
    
    confidence = state.get("confidence_score", 0.0)
    
    if confidence >= settings.agent_auto_apply_threshold:
        return "resolved"
    elif confidence >= settings.agent_suggest_threshold:
        # Medium confidence - still resolve but mark for user approval
        return "resolved"
    else:
        return "escalate"

