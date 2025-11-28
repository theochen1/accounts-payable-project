"""
Agent nodes for LangGraph workflow.
Each node represents a step in the agent's decision-making process.
"""
import json
import logging
from typing import Dict
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from app.config import settings
from app.agents.state import AgentState
from app.agents.tools import (
    fuzzy_match_vendor,
    get_historical_prices,
    validate_price_variance_policy,
    update_invoice_vendor
)

logger = logging.getLogger(__name__)


def create_llm():
    """Create OpenAI LLM instance."""
    return ChatOpenAI(
        model=settings.agent_model,
        temperature=settings.agent_temperature,
        api_key=settings.openai_api_key
    )


def create_analyze_node(db: Session):
    """Create analyze node with db access."""
    async def analyze_exception_node(state: AgentState) -> AgentState:
        """
        Analyze the matching exception and determine resolution strategy.
        """
        llm = create_llm()
        
        exception_type = state.get("exception_type", "unknown")
        invoice_data = state.get("invoice_data", {})
        po_data = state.get("po_data", {})
        matching_result = state.get("matching_result", {})
        
        prompt = f"""
        You are an AP automation expert analyzing an invoice matching exception.

        Exception Type: {exception_type}

        Invoice Details:
        - Vendor: {invoice_data.get('vendor_name', 'N/A')}
        - Total: {invoice_data.get('total_amount', 'N/A')} {invoice_data.get('currency', 'USD')}
        - PO Number: {invoice_data.get('po_number', 'N/A')}

        PO Details:
        - Vendor: {po_data.get('vendor_name', 'N/A')}
        - Total: {po_data.get('total_amount', 'N/A')} {po_data.get('currency', 'USD')}

        Matching Issues:
        {json.dumps(matching_result.get('issues', []), indent=2)}

        Analyze this exception and determine:
        1. Root cause of the mismatch
        2. Likelihood this can be auto-resolved (high/medium/low)
        3. Recommended resolution strategy
        4. Confidence score (0-1)

        Respond in JSON format:
        {{
            "root_cause": "...",
            "auto_resolve_likelihood": "high|medium|low",
            "strategy": "...",
            "confidence": 0.0-1.0,
            "reasoning": "..."
        }}
        """
        
        try:
            response = await llm.ainvoke(prompt)
            content = response.content
            
            # Try to parse JSON from response
            # LLM might wrap JSON in markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(content)
            
            state["reasoning"] = analysis.get("reasoning", "")
            state["confidence_score"] = float(analysis.get("confidence", 0.0))
            state["current_step"] = "analyzed"
            
            logger.info(f"Exception analysis completed. Confidence: {state['confidence_score']:.2f}")
            
        except Exception as e:
            logger.error(f"Error in analyze_exception_node: {e}")
            state["should_escalate"] = True
            state["escalation_reason"] = f"Failed to analyze exception: {str(e)}"
            state["current_step"] = "analysis_failed"
        
        return state
    return analyze_exception_node


def create_vendor_correction_node(db: Session):
    """Create vendor correction node with db access."""
    async def vendor_correction_node(state: AgentState) -> AgentState:
        """
        Attempt to auto-correct vendor mismatches using fuzzy matching.
        """
        invoice_data = state.get("invoice_data", {})
        invoice_vendor_name = invoice_data.get("vendor_name")
        invoice_id = int(state.get("invoice_id", 0))
        
        if not invoice_vendor_name:
            state["should_escalate"] = True
            state["escalation_reason"] = "Invoice vendor name is missing"
            state["current_step"] = "vendor_correction_failed"
            return state
        
        # Use fuzzy matching tool
        match_result = fuzzy_match_vendor(invoice_vendor_name, db)
        
        if match_result and match_result["confidence"] >= 0.85:
            state["resolution_action"] = "update_vendor"
            state["resolution_data"] = {
                "old_vendor_name": invoice_vendor_name,
                "new_vendor_id": match_result["vendor_id"],
                "new_vendor_name": match_result["vendor_name"],
                "match_confidence": match_result["confidence"]
            }
            state["confidence_score"] = match_result["confidence"]
            state["reasoning"] += f"\n\nFuzzy matched '{invoice_vendor_name}' to '{match_result['vendor_name']}' with {match_result['confidence']:.2%} confidence."
            state["should_escalate"] = False
            state["tools_used"].append({"tool": "fuzzy_match_vendor", "result": match_result})
        else:
            state["should_escalate"] = True
            confidence = match_result["confidence"] if match_result else 0.0
            state["escalation_reason"] = f"Could not confidently match vendor '{invoice_vendor_name}' (confidence: {confidence:.2%})"
            if match_result:
                state["tools_used"].append({"tool": "fuzzy_match_vendor", "result": match_result})
        
        state["current_step"] = "vendor_corrected"
        
        return state
    return vendor_correction_node


def create_price_variance_node(db: Session):
    """Create price variance node with db access."""
    async def price_variance_node(state: AgentState) -> AgentState:
        """
        Analyze and resolve price variances.
        """
        invoice_data = state.get("invoice_data", {})
        po_data = state.get("po_data", {})
        
        invoice_total = float(invoice_data.get("total_amount", 0))
        po_total = float(po_data.get("total_amount", 0))
        
        if po_total == 0:
            state["should_escalate"] = True
            state["escalation_reason"] = "PO total is zero, cannot calculate variance"
            state["current_step"] = "price_analysis_failed"
            return state
        
        variance_percent = abs((invoice_total - po_total) / po_total * 100)
        
        # Check policy
        vendor_id = po_data.get("vendor_id")
        if not vendor_id:
            state["should_escalate"] = True
            state["escalation_reason"] = "PO vendor ID is missing"
            state["current_step"] = "price_analysis_failed"
            return state
        
        policy_result = validate_price_variance_policy(
            variance_percent=variance_percent,
            po_value=po_total,
            vendor_id=vendor_id,
            db=db
        )
        
        state["tools_used"].append({"tool": "validate_price_variance_policy", "result": policy_result})
        
        if policy_result["within_policy"]:
            state["resolution_action"] = "approve_variance"
            state["resolution_data"] = {
                "variance_percent": variance_percent,
                "policy_threshold": policy_result["threshold"],
                "reason": policy_result["reasoning"],
                "invoice_total": invoice_total,
                "po_total": po_total
            }
            state["confidence_score"] = 0.9
            state["should_escalate"] = False
            state["reasoning"] += f"\n\nPrice variance {variance_percent:.2f}% is within policy limit of {policy_result['threshold']}%."
        else:
            # Check historical prices for justification
            # Get first line item SKU if available
            invoice_lines = invoice_data.get("invoice_lines", [])
            if invoice_lines and len(invoice_lines) > 0:
                first_line = invoice_lines[0] if isinstance(invoice_lines[0], dict) else invoice_lines[0]
                sku = first_line.get("sku") if isinstance(first_line, dict) else getattr(first_line, "sku", None)
                if sku:
                    historical_prices = get_historical_prices(sku, vendor_id, db)
                    state["tools_used"].append({"tool": "get_historical_prices", "result": {"count": len(historical_prices)}})
                    
                    if historical_prices:
                        avg_price = sum(p["price"] for p in historical_prices) / len(historical_prices)
                        state["reasoning"] += f"\n\nHistorical average price for SKU {sku}: ${avg_price:.2f}"
            
            state["should_escalate"] = True
            state["escalation_reason"] = f"Price variance {variance_percent:.2f}% exceeds policy limit of {policy_result['threshold']}%"
        
        state["current_step"] = "price_analyzed"
        
        return state
    return price_variance_node


def escalation_node(state: AgentState) -> AgentState:
    """
    Prepare exception for human escalation.
    """
    state["resolution_action"] = "escalate"
    state["should_escalate"] = True
    state["current_step"] = "escalated"
    
    if not state.get("escalation_reason"):
        state["escalation_reason"] = "Exception requires human review"
    
    logger.info(f"Exception escalated: {state['escalation_reason']}")
    
    return state


def finalize_node(state: AgentState) -> AgentState:
    """Final node to mark resolution complete."""
    state["current_step"] = "completed"
    logger.info(f"Agent workflow completed. Resolution: {state.get('resolution_action')}")
    return state
