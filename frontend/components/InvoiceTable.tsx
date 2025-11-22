'use client';

import { Invoice } from '@/lib/api';

interface InvoiceTableProps {
  invoices: Invoice[];
  onRowClick: (invoiceId: number) => void;
}

export default function InvoiceTable({ invoices, onRowClick }: InvoiceTableProps) {
  const getStatusClass = (status: string) => {
    return `status-badge status-${status}`;
  };

  const formatCurrency = (amount: number | undefined, currency: string) => {
    if (amount === undefined || amount === null) return 'N/A';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  if (invoices.length === 0) {
    return (
      <div className="card">
        <p>No invoices found.</p>
      </div>
    );
  }

  return (
    <table className="table">
      <thead>
        <tr>
          <th>Invoice Number</th>
          <th>Vendor</th>
          <th>PO Number</th>
          <th>Total</th>
          <th>Status</th>
          <th>Created</th>
        </tr>
      </thead>
      <tbody>
        {invoices.map((invoice) => (
          <tr key={invoice.id} onClick={() => onRowClick(invoice.id)}>
            <td>{invoice.invoice_number}</td>
            <td>{invoice.vendor_name || 'N/A'}</td>
            <td>{invoice.po_number || 'N/A'}</td>
            <td>{formatCurrency(invoice.total_amount, invoice.currency)}</td>
            <td>
              <span className={getStatusClass(invoice.status)}>
                {invoice.status.replace('_', ' ').toUpperCase()}
              </span>
            </td>
            <td>{formatDate(invoice.created_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

