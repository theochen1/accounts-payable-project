"""
Agent API router for invoice matching exception resolution.
"""
import uuid
import logging
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.invoice import Invoice
from app.models.purchase_order import PurchaseOrder
from app.models.agent_task import AgentTask
from app.schemas.agent import AgentTaskResponse, AgentTaskCreate
from app.schemas.matching import MatchingResult
from app.agents.orchestrator import create_agent_workflow
from app.agents.state import AgentState
from app.agents.tools import update_invoice_vendor
from app.services.matching_service import match_invoice_to_po
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])

# Import orchestrator
from app.agents.orchestrator import create_agent_workflow


@router.post("/resolve", response_model=AgentTaskResponse)
async def resolve_exception(
    invoice_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Trigger agent to resolve invoice matching exception.
    """
    # Get invoice and matching result
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Get PO if exists
    po = None
    if invoice.po_number:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == invoice.po_number).first()
    
    if not po:
        raise HTTPException(status_code=400, detail="Invoice has no associated PO")
    
    # Get or run matching
    matching_result = None
    if hasattr(invoice, 'matching_result') and invoice.matching_result:
        matching_result = invoice.matching_result
    else:
        # Run matching to get current result
        matching_result = match_invoice_to_po(db, invoice.id)
    
    if not matching_result or matching_result.status == "matched":
        raise HTTPException(status_code=400, detail="Invoice has no exceptions to resolve")
    
    # Determine exception type from first issue
    exception_type = "unknown"
    if matching_result.issues:
        exception_type = matching_result.issues[0].type
    
    # Create agent task record
    task_id = str(uuid.uuid4())
    agent_task = AgentTask(
        id=uuid.UUID(task_id),
        invoice_id=invoice_id,
        task_type=exception_type,
        status="pending",
        input_data={
            "invoice_data": {
                "id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "vendor_id": invoice.vendor_id,
                "vendor_name": invoice.vendor.name if invoice.vendor else None,
                "po_number": invoice.po_number,
                "total_amount": float(invoice.total_amount) if invoice.total_amount else None,
                "currency": invoice.currency,
                "invoice_lines": [
                    {
                        "line_no": line.line_no,
                        "sku": line.sku,
                        "description": line.description,
                        "quantity": float(line.quantity),
                        "unit_price": float(line.unit_price)
                    }
                    for line in invoice.invoice_lines
                ]
            },
            "po_data": {
                "id": po.id,
                "po_number": po.po_number,
                "vendor_id": po.vendor_id,
                "vendor_name": po.vendor.name if po.vendor else None,
                "total_amount": float(po.total_amount),
                "currency": po.currency,
                "po_lines": [
                    {
                        "line_no": line.line_no,
                        "sku": line.sku,
                        "description": line.description,
                        "quantity": float(line.quantity),
                        "unit_price": float(line.unit_price)
                    }
                    for line in po.po_lines
                ]
            },
            "matching_result": {
                "status": matching_result.status,
                "overall_match": matching_result.overall_match,
                "issues": [
                    {
                        "type": issue.type,
                        "severity": issue.severity,
                        "message": issue.message,
                        "details": issue.details
                    }
                    for issue in matching_result.issues
                ],
                "line_item_matches": [
                    {
                        "invoice_line_no": match.invoice_line_no,
                        "po_line_no": match.po_line_no,
                        "matched": match.matched,
                        "issues": match.issues
                    }
                    for match in matching_result.line_item_matches
                ]
            }
        }
    )
    db.add(agent_task)
    db.commit()
    db.refresh(agent_task)
    
    # Run agent workflow in background
    background_tasks.add_task(
        run_agent_workflow,
        task_id=task_id,
        invoice_id=invoice_id,
        db=db
    )
    
    return AgentTaskResponse(
        task_id=task_id,
        invoice_id=invoice_id,
        task_type=exception_type,
        status="pending",
        applied=False,
        created_at=agent_task.created_at
    )


async def run_agent_workflow(task_id: str, invoice_id: int, db: Session):
    """
    Execute the agent workflow (runs in background).
    """
    try:
        # Update task status
        task = db.query(AgentTask).filter(AgentTask.id == uuid.UUID(task_id)).first()
        if not task:
            logger.error(f"Agent task {task_id} not found")
            return
        
        task.status = "running"
        task.started_at = datetime.now()
        db.commit()
        
        # Get input data
        input_data = task.input_data
        invoice_data = input_data["invoice_data"]
        po_data = input_data["po_data"]
        matching_result = input_data["matching_result"]
        
        # Determine exception type
        exception_type = task.task_type
        
        # Prepare initial state
        initial_state = AgentState(
            invoice_id=str(invoice_id),
            invoice_data=invoice_data,
            po_data=po_data,
            matching_result=matching_result,
            exception_type=exception_type,
            current_step="initialized",
            confidence_score=0.0,
            reasoning="",
            tools_used=[],
            resolution_action=None,
            resolution_data=None,
            should_escalate=False,
            escalation_reason=None,
            iteration_count=0
        )
        
        # Create workflow with db session bound to nodes
        workflow = create_agent_workflow(settings.database_url, db=db)
        
        # Create a config with thread_id for checkpointer
        config = {"configurable": {"thread_id": task_id}}
        
        # Run workflow
        final_state = await workflow.ainvoke(initial_state, config=config)
        
        # Apply resolution if confidence is high enough
        if (not final_state.get("should_escalate", False) and 
            final_state.get("confidence_score", 0.0) >= settings.agent_auto_apply_threshold):
            
            apply_resolution(final_state, db)
            task.applied = True
            task.resolution_action = "auto_fixed"
        elif final_state.get("should_escalate", False):
            task.resolution_action = "escalated"
        else:
            task.resolution_action = "suggested"
        
        # Update task with results
        task.status = "completed"
        task.completed_at = datetime.now()
        task.confidence_score = final_state.get("confidence_score", 0.0)
        task.reasoning = final_state.get("reasoning", "")
        task.output_data = {
            "resolution_action": final_state.get("resolution_action"),
            "resolution_data": final_state.get("resolution_data"),
            "tools_used": final_state.get("tools_used", [])
        }
        db.commit()
        
        logger.info(f"Agent workflow completed for task {task_id}. Resolution: {task.resolution_action}")
        
    except Exception as e:
        logger.error(f"Agent workflow failed for task {task_id}: {str(e)}", exc_info=True)
        task = db.query(AgentTask).filter(AgentTask.id == uuid.UUID(task_id)).first()
        if task:
            task.status = "failed"
            task.error_message = str(e)
            db.commit()


def apply_resolution(state: AgentState, db: Session):
    """
    Apply the agent's resolution to the database.
    """
    action = state.get("resolution_action")
    data = state.get("resolution_data", {})
    invoice_id = int(state.get("invoice_id", 0))
    
    if not invoice_id:
        logger.error("Cannot apply resolution: invoice_id missing")
        return
    
    try:
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            logger.error(f"Invoice {invoice_id} not found")
            return
        
        if action == "update_vendor":
            # Update invoice vendor
            new_vendor_id = data.get("new_vendor_id")
            if new_vendor_id:
                success = update_invoice_vendor(invoice_id, new_vendor_id, db)
                if success:
                    # Re-run matching
                    new_result = match_invoice_to_po(db, invoice_id)
                    logger.info(f"Invoice {invoice_id}: Vendor updated and matching re-run")
        
        elif action == "approve_variance":
            # Update invoice status to approved
            invoice.status = "approved"
            logger.info(f"Invoice {invoice_id}: Approved with price variance")
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Failed to apply resolution: {e}", exc_info=True)
        db.rollback()


@router.get("/tasks/{task_id}", response_model=AgentTaskResponse)
def get_agent_task(task_id: str, db: Session = Depends(get_db)):
    """Get agent task status and results."""
    try:
        task = db.query(AgentTask).filter(AgentTask.id == uuid.UUID(task_id)).first()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return AgentTaskResponse(
        task_id=str(task.id),
        invoice_id=task.invoice_id,
        task_type=task.task_type,
        status=task.status,
        confidence_score=task.confidence_score,
        reasoning=task.reasoning,
        resolution_action=task.resolution_action,
        applied=task.applied,
        created_at=task.created_at,
        completed_at=task.completed_at,
        error_message=task.error_message,
        output_data=task.output_data
    )


@router.get("/tasks/invoice/{invoice_id}", response_model=List[AgentTaskResponse])
def get_invoice_agent_tasks(invoice_id: int, db: Session = Depends(get_db)):
    """Get all agent tasks for an invoice."""
    tasks = db.query(AgentTask).filter(AgentTask.invoice_id == invoice_id).order_by(AgentTask.created_at.desc()).all()
    
    return [
        AgentTaskResponse(
            task_id=str(task.id),
            invoice_id=task.invoice_id,
            task_type=task.task_type,
            status=task.status,
            confidence_score=task.confidence_score,
            reasoning=task.reasoning,
            resolution_action=task.resolution_action,
            applied=task.applied,
            created_at=task.created_at,
            completed_at=task.completed_at,
            error_message=task.error_message,
            output_data=task.output_data
        )
        for task in tasks
    ]

