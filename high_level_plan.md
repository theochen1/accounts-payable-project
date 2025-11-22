You are an expert full‑stack engineer helping build an MVP for an agentic AI accounts payable platform focused on PO‑backed PDF invoices.

## Project context

The product is a manager-facing web app that lets an AP / procurement manager quickly process a queue of PO-backed invoices.  
The manager should be able to upload or view ingested PDF invoices, see which ones match purchase orders, and resolve mismatches or exceptions through a simple interface.  
The current scope is ONLY PO-backed invoices (no non-PO invoices) and ONLY PDF scans as input for the initial build.  

## High-level architecture

- Backend: Python (FastAPI) with a REST API.
- Data: Postgres as the main database (can be hosted via Supabase / Neon / Railway or similar).
- Storage: Object storage (e.g., an S3-like bucket) for raw PDF files and optionally OCR JSON blobs.
- OCR: DeepSeek-OCR accessed via an HTTP API (assume we can call a hosted endpoint that returns structured JSON for a given PDF).
- Matching/logic: Deterministic matching and rule-based validation for the MVP (no complex ML training yet).
- Frontend: React or Next.js app that talks to the backend via JSON APIs.
- Hosting: Prefer simple, managed platforms (e.g., Vercel for frontend, Render/Fly/Railway/etc. for backend and DB).

You should assume there is NO real SAP/Oracle integration yet; instead, implement a “fake ERP” using our own Postgres tables for vendors, purchase orders, and goods receipts.

## Core user flow to implement

1. Manager visits the web app and sees a list/queue of invoices with basic info (invoice number, vendor, PO number, total, status).  
2. Manager can upload a new PDF invoice:
   - Frontend sends the file to the backend.
   - Backend stores the PDF in object storage and calls DeepSeek-OCR.
   - OCR returns structured fields in JSON (vendor, invoice number, PO number, totals, line items, etc.).
   - Backend saves the extracted data into the database and runs matching/validation logic.
3. Matching/validation logic:
   - Look up the referenced PO by PO number from our Postgres tables.
   - Perform 2‑way matching (invoice vs PO) on:
     - Vendor
     - Currency
     - Header total (with small tolerance)
     - Line items (by SKU or description, comparing quantity and unit price).
   - Compute a status such as:
     - "Matched / Auto-approvable"
     - "Needs Manager Review"
     - "Exception (e.g., missing PO, large mismatch)"
4. Manager can click into an invoice detail view:
   - See the invoice PDF preview.
   - See extracted invoice fields.
   - See PO details and line items side by side.
   - See mismatches highlighted.
   - See a suggested action (approve, reject, or route).
5. Manager can take an action:
   - Approve → mark invoice as approved in DB.
   - Reject → mark as rejected and store a reason.
   - Route → store that the invoice should be routed (for now, just write the routing target and reason into DB; actual emailing can be simulated or stubbed).

## Data model (initial)

Design a simple schema in Postgres with at least these tables (you can refine names and columns as you implement):

- vendors
  - id
  - name
  - tax_id (optional)
  - default_currency
  - supplier_email (for future routing)
  - created_at / updated_at

- purchase_orders
  - id
  - po_number (unique)
  - vendor_id (FK to vendors)
  - total_amount
  - currency
  - status
  - requester_email (internal person who requested)
  - created_at / updated_at

- po_lines
  - id
  - po_id (FK to purchase_orders)
  - line_no
  - sku (or item_code)
  - description
  - quantity
  - unit_price

- invoices
  - id
  - invoice_number
  - vendor_id (FK to vendors)
  - po_number (string, used for lookup)
  - invoice_date
  - total_amount
  - currency
  - pdf_storage_path (where the raw PDF lives)
  - ocr_json (JSONB, storing raw OCR output)
  - status (e.g., "new", "matched", "needs_review", "exception", "approved", "rejected")
  - created_at / updated_at

- invoice_lines
  - id
  - invoice_id (FK to invoices)
  - line_no
  - sku
  - description
  - quantity
  - unit_price

- decisions
  - id
  - invoice_id (FK to invoices)
  - user_identifier (string; we can hard-code a manager user for now)
  - decision ("approved", "rejected", "routed")
  - reason (text, optional)
  - created_at

You may propose adjustments to this schema as you implement, but keep it simple and focused on enabling the core flow.

## Matching and business rules

Implement the initial matching logic as pure Python functions that operate on invoice + PO records from the database:

- If there is no PO with the given PO number → status "exception: missing_po".
- If vendor on the invoice does not match the PO’s vendor → status "exception: vendor_mismatch".
- If currencies differ → "exception: currency_mismatch".
- If total amount differs by more than a small configurable tolerance → "needs_review: total_mismatch".
- For each invoice line:
  - Attempt to match it to a PO line by SKU (or fallback to fuzzy/substring match on description).
  - Compare quantity and unit price.
  - Record any mismatches in a structured way (e.g., a JSON list of issues).

Aggregate all issues into a match result object that the frontend can display (e.g., per-line differences and an overall status).

## Frontend requirements

Build a minimal but clean UI with at least:

1. Invoice list (queue) page:
   - Table with columns: invoice number, vendor, PO number, total, status, created date.
   - Filters by status (Matched, Needs review, Exception, Approved, Rejected).
   - Ability to click a row to open the detail view.

2. Invoice detail page:
   - Show the PDF (or at least a link to download/view it).
   - Show extracted invoice fields.
   - Show the matched PO and its line items.
   - Clearly highlight mismatches / issues.
   - Show suggested action.
   - Provide buttons to Approve, Reject, or Route, with an optional text area for comments.

The UI should prioritize clarity and fast decision-making by the manager, not visual complexity.

## Implementation guidance

- Before writing code, briefly outline the file/folder structure for:
  - backend (FastAPI app, models, services, routers)
  - frontend (pages/components for list and detail views)
  - scripts or notebooks for seeding synthetic vendor/PO/invoice data.
- Prefer clear, explicit code over clever abstractions.
- Keep configuration (DB URLs, OCR endpoint, etc.) in environment variables.
- Write small, composable functions for:
  - Running OCR and normalizing its output.
  - Performing matching and returning a structured summary.
  - Converting DB models into API response DTOs.
- Generate a small synthetic dataset (e.g., script or fixture) so we can quickly spin up a seeded DB and demo the flow end-to-end.

## How I want you to behave in this repo

- When asked to "set up" or "modify" parts of the system, propose a short plan first, then implement it step-by-step.
- When you create new files or major changes, summarize what you did and why.
- When there are multiple reasonable choices (e.g., field naming, folder structure), briefly explain the tradeoffs and pick one.
- Avoid overcomplicating architecture; this is an MVP optimized for a demo of the end-to-end flow described above.
- Always keep the main user journey in mind: a manager quickly triaging and approving/reviewing PO-backed PDF invoices.
