'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { invoiceApi, Invoice } from '@/lib/api';
import InvoiceTable from '@/components/InvoiceTable';

export default function Home() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const router = useRouter();

  useEffect(() => {
    loadInvoices();
  }, [statusFilter]);

  const loadInvoices = async () => {
    try {
      setLoading(true);
      const params: any = {};
      if (statusFilter) {
        params.status = statusFilter;
      }
      const data = await invoiceApi.list(params);
      setInvoices(data);
    } catch (error) {
      console.error('Failed to load invoices:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRowClick = (invoiceId: number) => {
    router.push(`/invoices/${invoiceId}`);
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      await invoiceApi.upload(file);
      loadInvoices();
      alert('Invoice uploaded successfully!');
    } catch (error: any) {
      alert(`Failed to upload invoice: ${error.message}`);
    }
  };

  return (
    <div className="container">
      <div className="header">
        <h1>Accounts Payable - Invoice Queue</h1>
      </div>

      <div style={{ marginBottom: '20px', display: 'flex', gap: '16px', alignItems: 'center' }}>
        <div>
          <label htmlFor="status-filter" style={{ marginRight: '8px' }}>Filter by Status:</label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }}
          >
            <option value="">All</option>
            <option value="new">New</option>
            <option value="matched">Matched</option>
            <option value="needs_review">Needs Review</option>
            <option value="exception">Exception</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="routed">Routed</option>
          </select>
        </div>

        <div>
          <label htmlFor="file-upload" className="button button-primary" style={{ cursor: 'pointer', display: 'inline-block' }}>
            Upload Invoice PDF
          </label>
          <input
            id="file-upload"
            type="file"
            accept=".pdf"
            onChange={handleFileUpload}
            style={{ display: 'none' }}
          />
        </div>
      </div>

      {loading ? (
        <div>Loading...</div>
      ) : (
        <InvoiceTable invoices={invoices} onRowClick={handleRowClick} />
      )}
    </div>
  );
}

