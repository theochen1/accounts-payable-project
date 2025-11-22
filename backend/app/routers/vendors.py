from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.vendor import Vendor
from app.schemas.vendor import VendorResponse

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


@router.get("", response_model=List[VendorResponse])
def list_vendors(db: Session = Depends(get_db)):
    """List all vendors"""
    vendors = db.query(Vendor).all()
    return vendors

