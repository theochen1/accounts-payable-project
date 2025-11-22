# Accounts Payable Platform MVP

A manager-facing web application for processing PO-backed PDF invoices with automated OCR extraction and matching logic.

## Architecture

- **Backend**: FastAPI (Python) with REST API
- **Database**: PostgreSQL (SQLAlchemy ORM)
- **Storage**: S3-compatible object storage (or local filesystem fallback)
- **OCR**: DeepSeek-OCR HTTP API integration
- **Frontend**: Next.js (React) with TypeScript
- **Matching**: Deterministic rule-based matching between invoices and purchase orders

## Project Structure

```
accounts-payable-project/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── models/      # SQLAlchemy models
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── services/    # Business logic (OCR, storage, matching)
│   │   ├── routers/     # API endpoints
│   │   └── utils/       # Utility functions
│   ├── alembic/         # Database migrations
│   └── scripts/         # Seed data script
├── frontend/            # Next.js frontend
│   ├── app/             # Next.js app directory
│   ├── components/      # React components
│   └── lib/             # API client
└── README.md
```

## Setup Instructions

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL database (local or hosted)
- DeepSeek-OCR API access (or configure endpoint)

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```

5. Update `.env` with your configuration:
   - Database URL (PostgreSQL connection string)
   - DeepSeek-OCR API URL and API key
   - Storage configuration (S3 or leave empty for local filesystem)

6. Run database migrations:
   ```bash
   alembic upgrade head
   ```

7. (Optional) Seed the database with synthetic data:
   ```bash
   python scripts/seed_data.py
   ```

8. Start the backend server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Create a `.env.local` file:
   ```bash
   cp .env.example .env.local
   ```

4. Update `.env.local` with your backend API URL:
   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

5. Start the development server:
   ```bash
   npm run dev
   ```

The frontend will be available at `http://localhost:3000`

## Usage

### Core User Flow

1. **View Invoice Queue**: Navigate to the home page to see all invoices with their status
2. **Upload Invoice**: Click "Upload Invoice PDF" to upload a new PDF invoice
   - The system will automatically:
     - Store the PDF in object storage
     - Process it through DeepSeek-OCR
     - Extract structured data
     - Match it against purchase orders
     - Set the appropriate status
3. **Review Invoice**: Click on any invoice row to view details
   - See extracted invoice fields
   - View matched purchase order
   - Review matching results and issues
4. **Take Action**: 
   - **Approve**: Mark invoice as approved (for matched/needs_review status)
   - **Reject**: Reject invoice with a reason
   - **Route**: Route invoice to another person/process

### Invoice Statuses

- **new**: Just uploaded, matching in progress
- **matched**: Fully matched with PO, auto-approvable
- **needs_review**: Has mismatches but within tolerance
- **exception**: Missing PO, vendor mismatch, currency mismatch, or large total mismatch
- **approved**: Manager approved the invoice
- **rejected**: Manager rejected the invoice
- **routed**: Invoice routed to another process

### Matching Logic

The system performs 2-way matching between invoices and purchase orders:

1. **PO Existence**: Checks if the referenced PO exists
2. **Vendor Match**: Verifies invoice vendor matches PO vendor
3. **Currency Match**: Ensures currencies match
4. **Total Match**: Compares total amounts (configurable tolerance, default 1%)
5. **Line Item Match**: Matches line items by SKU (fallback to description fuzzy match)
   - Compares quantities and unit prices
   - Reports mismatches per line

## API Endpoints

### Invoices

- `GET /api/invoices` - List invoices (with filters: status, vendor_id)
- `GET /api/invoices/{id}` - Get invoice detail with PO and matching results
- `POST /api/invoices/upload` - Upload PDF invoice
- `POST /api/invoices/{id}/approve` - Approve invoice
- `POST /api/invoices/{id}/reject` - Reject invoice
- `POST /api/invoices/{id}/route` - Route invoice

### Purchase Orders

- `GET /api/purchase-orders/{po_number}` - Get PO details

### Vendors

- `GET /api/vendors` - List all vendors

## Configuration

### Matching Tolerance

The matching tolerance for total amounts can be configured via `MATCHING_TOLERANCE` environment variable (default: 0.01 = 1%).

### Storage

If S3 credentials are not provided, the system falls back to local filesystem storage in `local_storage/invoices/`.

### OCR Integration

The OCR service expects the DeepSeek-OCR API to return structured JSON with:
- `vendor_name` or `vendor.name`
- `invoice_number` or `invoice_no`
- `po_number` or `purchase_order_number`
- `invoice_date` or `date`
- `total_amount` or `total`
- `currency`
- `line_items` array with `sku`, `description`, `quantity`, `unit_price`

Adjust the `_normalize_ocr_response` method in `backend/app/services/ocr_service.py` to match your OCR API's response format.

## Development

### Running Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

### Seeding Data

The seed script creates:
- 8 vendors
- 12 purchase orders with line items
- 12 invoices with various matching scenarios:
  - 4 matched invoices
  - 3 invoices needing review
  - 5 invoices with exceptions (missing PO, vendor mismatch, currency mismatch, large total mismatch)

Run: `python backend/scripts/seed_data.py`

## Deployment

### Backend

The backend can be deployed to:
- Render
- Fly.io
- Railway
- Heroku
- Any platform supporting Python/FastAPI

Ensure environment variables are set in your deployment platform.

### Frontend

The frontend can be deployed to:
- Vercel (recommended for Next.js)
- Netlify
- Any static hosting service

Set `NEXT_PUBLIC_API_URL` to your backend API URL.

## Future Enhancements

- Real ERP integration (SAP/Oracle)
- Email notifications for routing
- Advanced ML-based matching
- Multi-currency support with conversion
- Approval workflows
- Audit logging
- PDF preview in browser
- Batch invoice upload

## License

MIT

