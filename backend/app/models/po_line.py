from sqlalchemy import Column, Integer, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class POLine(Base):
    __tablename__ = "po_lines"

    id = Column(Integer, primary_key=True, index=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    line_no = Column(Integer, nullable=False)
    sku = Column(String, nullable=True, index=True)
    description = Column(String, nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)

    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="po_lines")

