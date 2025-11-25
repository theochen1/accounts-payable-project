from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal
from app.database import get_db
from app.models.purchase_order import PurchaseOrder
from app.models.po_line import POLine
from app.models.vendor import Vendor
from app.schemas.po import POResponse, POListResponse, POCreate, POLineResponse

router = APIRouter(prefix="/api/purchase-orders", tags=["purchase-orders"])


@router.get("", response_model=List[POListResponse])
def list_purchase_orders(
    vendor_id: Optional[int] = Query(None, description="Filter by vendor ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """List all purchase orders with optional filters"""
    query = db.query(PurchaseOrder)
    
    if vendor_id:
        query = query.filter(PurchaseOrder.vendor_id == vendor_id)
    if status:
        query = query.filter(PurchaseOrder.status == status)
    
    pos = query.order_by(PurchaseOrder.created_at.desc()).offset(skip).limit(limit).all()
    
    # Enrich with vendor names
    result = []
    for po in pos:
        vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
        result.append(POListResponse(
            id=po.id,
            po_number=po.po_number,
            vendor_id=po.vendor_id,
            vendor_name=vendor.name if vendor else None,
            total_amount=po.total_amount,
            currency=po.currency,
            status=po.status,
            created_at=po.created_at
        ))
    
    return result


@router.get("/{po_number}", response_model=POResponse)
def get_purchase_order(po_number: str, db: Session = Depends(get_db)):
    """Get purchase order details by PO number"""
    po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == po_number).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    
    # Get vendor name
    vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
    
    po_lines = [
        POLineResponse(
            id=line.id,
            line_no=line.line_no,
            sku=line.sku,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price
        )
        for line in po.po_lines
    ]
    
    return POResponse(
        id=po.id,
        po_number=po.po_number,
        vendor_id=po.vendor_id,
        vendor_name=vendor.name if vendor else None,
        total_amount=po.total_amount,
        currency=po.currency,
        status=po.status,
        requester_email=po.requester_email,
        created_at=po.created_at,
        updated_at=po.updated_at,
        po_lines=po_lines
    )


@router.post("", response_model=POResponse)
def create_purchase_order(po_data: POCreate, db: Session = Depends(get_db)):
    """Create a new purchase order"""
    # Check if PO number already exists
    existing_po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == po_data.po_number).first()
    if existing_po:
        raise HTTPException(status_code=400, detail=f"Purchase order with number {po_data.po_number} already exists")
    
    # Verify vendor exists
    vendor = db.query(Vendor).filter(Vendor.id == po_data.vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail=f"Vendor with ID {po_data.vendor_id} not found")
    
    # Calculate total from line items
    total = Decimal('0.00')
    for line in po_data.po_lines:
        total += Decimal(str(line.quantity)) * Decimal(str(line.unit_price))
    
    # Create PO
    po = PurchaseOrder(
        po_number=po_data.po_number,
        vendor_id=po_data.vendor_id,
        total_amount=total,
        currency=po_data.currency,
        status=po_data.status,
        requester_email=po_data.requester_email
    )
    db.add(po)
    db.flush()  # Get the ID
    
    # Create PO lines
    for line_data in po_data.po_lines:
        po_line = POLine(
            po_id=po.id,
            line_no=line_data.line_no,
            sku=line_data.sku,
            description=line_data.description,
            quantity=Decimal(str(line_data.quantity)),
            unit_price=Decimal(str(line_data.unit_price))
        )
        db.add(po_line)
    
    db.commit()
    db.refresh(po)
    
    # Return with vendor name
    return POResponse(
        id=po.id,
        po_number=po.po_number,
        vendor_id=po.vendor_id,
        vendor_name=vendor.name,
        total_amount=po.total_amount,
        currency=po.currency,
        status=po.status,
        requester_email=po.requester_email,
        created_at=po.created_at,
        updated_at=po.updated_at,
        po_lines=[
            POLineResponse(
                id=line.id,
                line_no=line.line_no,
                sku=line.sku,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price
            )
            for line in po.po_lines
        ]
    )

