"""
Seed script to generate synthetic vendor, PO, and invoice data for demo purposes
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models.vendor import Vendor
from app.models.purchase_order import PurchaseOrder
from app.models.po_line import POLine
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from decimal import Decimal
from datetime import date, datetime, timedelta
from faker import Faker

fake = Faker()


def create_vendors(db: Session, count: int = 8) -> list[Vendor]:
    """Create synthetic vendors"""
    vendors = []
    for _ in range(count):
        vendor = Vendor(
            name=fake.company(),
            tax_id=fake.bothify(text='##-#######'),
            default_currency=fake.random_element(elements=('USD', 'EUR', 'GBP')),
            supplier_email=fake.email()
        )
        db.add(vendor)
        vendors.append(vendor)
    db.commit()
    return vendors


def create_purchase_orders(db: Session, vendors: list[Vendor], count: int = 12) -> list[PurchaseOrder]:
    """Create synthetic purchase orders with line items"""
    pos = []
    for i in range(count):
        vendor = fake.random_element(elements=vendors)
        po = PurchaseOrder(
            po_number=f"PO-{2024}-{str(i+1).zfill(4)}",
            vendor_id=vendor.id,
            total_amount=Decimal('0.00'),
            currency=vendor.default_currency,
            status=fake.random_element(elements=('open', 'partially_received', 'closed')),
            requester_email=fake.email()
        )
        db.add(po)
        db.flush()  # Get the ID
        
        # Create line items
        num_lines = fake.random_int(min=2, max=5)
        total = Decimal('0.00')
        for line_no in range(1, num_lines + 1):
            quantity = Decimal(str(fake.random_int(min=1, max=100)))
            unit_price = Decimal(str(round(fake.random.uniform(10.0, 500.0), 2)))
            line_total = quantity * unit_price
            total += line_total
            
            po_line = POLine(
                po_id=po.id,
                line_no=line_no,
                sku=f"SKU-{fake.random_int(min=1000, max=9999)}",
                description=fake.catch_phrase(),
                quantity=quantity,
                unit_price=unit_price
            )
            db.add(po_line)
        
        po.total_amount = total
        pos.append(po)
    
    db.commit()
    return pos


def create_invoices(db: Session, vendors: list[Vendor], pos: list[PurchaseOrder]):
    """Create synthetic invoices with various matching scenarios"""
    invoices = []
    
    # Create some matched invoices
    for i in range(4):
        po = fake.random_element(elements=pos)
        vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
        
        # Perfect match
        invoice = Invoice(
            invoice_number=f"INV-{2024}-{str(i+1).zfill(4)}",
            vendor_id=po.vendor_id,
            po_number=po.po_number,
            invoice_date=date.today() - timedelta(days=fake.random_int(min=1, max=30)),
            total_amount=po.total_amount,  # Exact match
            currency=po.currency,
            pdf_storage_path=f"invoices/inv_{i+1}.pdf",
            ocr_json={"status": "processed"},
            status="matched"
        )
        db.add(invoice)
        db.flush()
        
        # Create invoice lines matching PO lines
        for po_line in po.po_lines:
            invoice_line = InvoiceLine(
                invoice_id=invoice.id,
                line_no=po_line.line_no,
                sku=po_line.sku,
                description=po_line.description,
                quantity=po_line.quantity,
                unit_price=po_line.unit_price
            )
            db.add(invoice_line)
        
        invoices.append(invoice)
    
    # Create invoices that need review (small mismatches)
    for i in range(3):
        po = fake.random_element(elements=pos)
        vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
        
        # Small total mismatch (within tolerance)
        total_diff = po.total_amount * Decimal('0.005')  # 0.5% difference
        invoice = Invoice(
            invoice_number=f"INV-{2024}-{str(i+5).zfill(4)}",
            vendor_id=po.vendor_id,
            po_number=po.po_number,
            invoice_date=date.today() - timedelta(days=fake.random_int(min=1, max=30)),
            total_amount=po.total_amount + total_diff,
            currency=po.currency,
            pdf_storage_path=f"invoices/inv_{i+5}.pdf",
            ocr_json={"status": "processed"},
            status="needs_review"
        )
        db.add(invoice)
        db.flush()
        
        # Create invoice lines with small mismatches
        for po_line in po.po_lines:
            qty_diff = po_line.quantity * Decimal('0.02')  # 2% quantity difference
            invoice_line = InvoiceLine(
                invoice_id=invoice.id,
                line_no=po_line.line_no,
                sku=po_line.sku,
                description=po_line.description,
                quantity=po_line.quantity + qty_diff,
                unit_price=po_line.unit_price
            )
            db.add(invoice_line)
        
        invoices.append(invoice)
    
    # Create invoices with exceptions
    # Missing PO
    po = fake.random_element(elements=pos)
    vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
    invoice = Invoice(
        invoice_number=f"INV-{2024}-{str(9).zfill(4)}",
        vendor_id=po.vendor_id,
        po_number="PO-NONEXISTENT-001",  # Non-existent PO
        invoice_date=date.today() - timedelta(days=fake.random_int(min=1, max=30)),
        total_amount=Decimal(str(round(fake.random.uniform(1000.0, 5000.0), 2))),
        currency=po.currency,
        pdf_storage_path=f"invoices/inv_9.pdf",
        ocr_json={"status": "processed"},
        status="exception"
    )
    db.add(invoice)
    db.flush()
    invoices.append(invoice)
    
    # Vendor mismatch
    po = fake.random_element(elements=pos)
    wrong_vendor = fake.random_element(elements=[v for v in vendors if v.id != po.vendor_id])
    invoice = Invoice(
        invoice_number=f"INV-{2024}-{str(10).zfill(4)}",
        vendor_id=wrong_vendor.id,  # Wrong vendor
        po_number=po.po_number,
        invoice_date=date.today() - timedelta(days=fake.random_int(min=1, max=30)),
        total_amount=po.total_amount,
        currency=po.currency,
        pdf_storage_path=f"invoices/inv_10.pdf",
        ocr_json={"status": "processed"},
        status="exception"
    )
    db.add(invoice)
    db.flush()
    invoices.append(invoice)
    
    # Currency mismatch
    po = fake.random_element(elements=pos)
    vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
    wrong_currency = fake.random_element(elements=[c for c in ['USD', 'EUR', 'GBP'] if c != po.currency])
    invoice = Invoice(
        invoice_number=f"INV-{2024}-{str(11).zfill(4)}",
        vendor_id=po.vendor_id,
        po_number=po.po_number,
        invoice_date=date.today() - timedelta(days=fake.random_int(min=1, max=30)),
        total_amount=po.total_amount,
        currency=wrong_currency,  # Wrong currency
        pdf_storage_path=f"invoices/inv_11.pdf",
        ocr_json={"status": "processed"},
        status="exception"
    )
    db.add(invoice)
    db.flush()
    invoices.append(invoice)
    
    # Large total mismatch
    po = fake.random_element(elements=pos)
    vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
    invoice = Invoice(
        invoice_number=f"INV-{2024}-{str(12).zfill(4)}",
        vendor_id=po.vendor_id,
        po_number=po.po_number,
        invoice_date=date.today() - timedelta(days=fake.random_int(min=1, max=30)),
        total_amount=po.total_amount * Decimal('1.15'),  # 15% difference
        currency=po.currency,
        pdf_storage_path=f"invoices/inv_12.pdf",
        ocr_json={"status": "processed"},
        status="exception"
    )
    db.add(invoice)
    db.flush()
    invoices.append(invoice)
    
    db.commit()
    return invoices


def main():
    """Main seeding function"""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        print("Creating vendors...")
        vendors = create_vendors(db, count=8)
        print(f"Created {len(vendors)} vendors")
        
        print("Creating purchase orders...")
        pos = create_purchase_orders(db, vendors, count=12)
        print(f"Created {len(pos)} purchase orders")
        
        print("Creating invoices...")
        invoices = create_invoices(db, vendors, pos)
        print(f"Created {len(invoices)} invoices")
        
        print("\nSeeding complete!")
        print(f"Summary:")
        print(f"  - Vendors: {len(vendors)}")
        print(f"  - Purchase Orders: {len(pos)}")
        print(f"  - Invoices: {len(invoices)}")
        print(f"    - Matched: 4")
        print(f"    - Needs Review: 3")
        print(f"    - Exceptions: 5")
        
    except Exception as e:
        print(f"Error during seeding: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

