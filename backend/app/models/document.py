from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base


class Document(Base):
    """
    Represents an uploaded document in the processing queue.
    Documents are uploaded first, then the user selects type (invoice/po),
    processes with OCR, reviews the pre-filled form, and saves to the final table.
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    document_type = Column(String, nullable=True)  # 'invoice' | 'po' | null (not yet selected)
    status = Column(String, default="pending", index=True)  # pending, processing, processed, error
    error_message = Column(String, nullable=True)
    ocr_data = Column(JSON, nullable=True)  # Stores OCR extraction results before final save
    processed_id = Column(Integer, nullable=True)  # ID of created Invoice or PurchaseOrder
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

