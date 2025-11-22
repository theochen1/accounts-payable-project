from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.purchase_order import PurchaseOrder
from app.models.vendor import Vendor
from app.schemas.po import POResponse

router = APIRouter(prefix="/api/purchase-orders", tags=["purchase-orders"])


@router.get("/{po_number}", response_model=POResponse)
def get_purchase_order(po_number: str, db: Session = Depends(get_db)):
    """Get purchase order details by PO number"""
    po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == po_number).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    
    # Get vendor name
    vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
    
    from app.schemas.po import POLineResponse
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

