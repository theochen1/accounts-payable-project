from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class VendorResponse(BaseModel):
    id: int
    name: str
    tax_id: Optional[str]
    default_currency: str
    supplier_email: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

