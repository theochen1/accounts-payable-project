'use client';

import { InvoiceDetail as InvoiceDetailType } from '@/lib/api';

interface InvoiceDetailProps {
  invoice: InvoiceDetailType;
}

export default function InvoiceDetailView({ invoice }: InvoiceDetailProps) {
  const formatCurrency = (amount: number | undefined, currency: string) => {
    if (amount === undefined || amount === null) return 'N/A';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
    }).format(amount);
  };

  const formatDate = (dateString: string | undefined) => {
    if (!dateString) return 'N/A';
    
    // For date-only strings (YYYY-MM-DD), parse without timezone conversion
    // to avoid off-by-one day errors
    if (dateString.match(/^\d{4}-\d{2}-\d{2}$/)) {
      // Parse YYYY-MM-DD directly without timezone conversion
      const [year, month, day] = dateString.split('-').map(Number);
      const date = new Date(year, month - 1, day);
      return date.toLocaleDateString();
    }
    
    // For datetime strings, use standard parsing
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusClass = (status: string) => {
    return `status-badge status-${status}`;
  };

  return (
    <div className="card">
      <h2>Invoice Details</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
        <div className="form-group">
          <label>Invoice Number</label>
          <div>{invoice.invoice_number}</div>
        </div>
        <div className="form-group">
          <label>Status</label>
          <div>
            <span className={getStatusClass(invoice.status)}>
              {invoice.status.replace('_', ' ').toUpperCase()}
            </span>
          </div>
        </div>
        <div className="form-group">
          <label>Vendor</label>
          <div>{invoice.vendor_name || 'N/A'}</div>
        </div>
        <div className="form-group">
          <label>PO Number</label>
          <div>{invoice.po_number || 'N/A'}</div>
        </div>
        <div className="form-group">
          <label>Invoice Date</label>
          <div>{formatDate(invoice.invoice_date)}</div>
        </div>
        <div className="form-group">
          <label>Total Amount</label>
          <div>{formatCurrency(invoice.total_amount, invoice.currency)}</div>
        </div>
        <div className="form-group">
          <label>Currency</label>
          <div>{invoice.currency}</div>
        </div>
        <div className="form-group">
          <label>Created</label>
          <div>{formatDate(invoice.created_at)}</div>
        </div>
      </div>

      {invoice.pdf_storage_path && (
        <div style={{ marginTop: '20px' }}>
          <label>PDF</label>
          <div>
            <a
              href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/storage/${invoice.pdf_storage_path}`}
              target="_blank"
              rel="noopener noreferrer"
              className="button button-primary"
            >
              View PDF
            </a>
          </div>
        </div>
      )}

      {invoice.invoice_lines && invoice.invoice_lines.length > 0 && (
        <div style={{ marginTop: '20px' }}>
          <h3>Line Items</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Line</th>
                <th>SKU</th>
                <th>Description</th>
                <th>Quantity</th>
                <th>Unit Price</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {invoice.invoice_lines.map((line) => (
                <tr key={line.id}>
                  <td>{line.line_no}</td>
                  <td>{line.sku || 'N/A'}</td>
                  <td>{line.description}</td>
                  <td>{line.quantity}</td>
                  <td>{formatCurrency(line.unit_price, invoice.currency)}</td>
                  <td>{formatCurrency(line.quantity * line.unit_price, invoice.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

