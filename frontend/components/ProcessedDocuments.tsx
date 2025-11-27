'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ProcessedDocument } from '@/lib/api';

interface ProcessedDocumentsProps {
  documents: ProcessedDocument[];
  loading?: boolean;
}

export default function ProcessedDocuments({
  documents,
  loading = false,
}: ProcessedDocumentsProps) {
  const router = useRouter();
  const [typeFilter, setTypeFilter] = useState<string>('');

  const filteredDocuments = typeFilter
    ? documents.filter(d => d.document_type === typeFilter)
    : documents;

  const handleRowClick = (doc: ProcessedDocument) => {
    if (doc.document_type === 'invoice') {
      router.push(`/invoices/${doc.id}`);
    } else if (doc.document_type === 'po') {
      router.push(`/purchase-orders/${doc.reference_number}`);
    }
  };

  const formatDate = (dateString: string | undefined) => {
    if (!dateString) return '-';
    const date = new Date(dateString + 'T00:00:00Z');
    return date.toLocaleDateString();
  };

  const formatAmount = (amount: number | undefined, currency: string) => {
    if (amount === undefined || amount === null) return '-';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
    }).format(amount);
  };

  const getTypeBadge = (type: string) => {
    if (type === 'invoice') {
      return <span className="type-badge invoice">Invoice</span>;
    } else if (type === 'po') {
      return <span className="type-badge po">PO</span>;
    }
    return null;
  };

  const getStatusBadge = (status: string) => {
    const statusClass = status.toLowerCase().replace(/_/g, '-');
    return <span className={`status-badge ${statusClass}`}>{status}</span>;
  };

  if (loading) {
    return <div className="loading">Loading processed documents...</div>;
  }

  return (
    <div className="processed-documents">
      <div className="header">
        <h2>Processed Documents</h2>
        <div className="filter">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="">All Types</option>
            <option value="invoice">Invoices</option>
            <option value="po">Purchase Orders</option>
          </select>
        </div>
      </div>

      {filteredDocuments.length === 0 ? (
        <div className="empty-state">
          No processed documents yet. Upload and process documents above.
        </div>
      ) : (
        <table className="documents-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Reference #</th>
              <th>Vendor</th>
              <th>Date</th>
              <th>Amount</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {filteredDocuments.map((doc) => (
              <tr
                key={`${doc.document_type}-${doc.id}`}
                onClick={() => handleRowClick(doc)}
              >
                <td>{getTypeBadge(doc.document_type)}</td>
                <td className="reference">{doc.reference_number}</td>
                <td>{doc.vendor_name || '-'}</td>
                <td>{formatDate(doc.date)}</td>
                <td>{formatAmount(doc.total_amount, doc.currency)}</td>
                <td>{getStatusBadge(doc.status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <style jsx>{`
        .processed-documents {
          background: white;
          border-radius: 12px;
          border: 1px solid #e5e7eb;
          overflow: hidden;
        }

        .header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 16px 20px;
          border-bottom: 1px solid #e5e7eb;
        }

        .header h2 {
          margin: 0;
          font-size: 18px;
          color: #1f2937;
        }

        .filter select {
          padding: 8px 12px;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          font-size: 14px;
        }

        .loading {
          padding: 40px;
          text-align: center;
          color: #6b7280;
        }

        .empty-state {
          padding: 40px;
          text-align: center;
          color: #6b7280;
        }

        .documents-table {
          width: 100%;
          border-collapse: collapse;
        }

        .documents-table th,
        .documents-table td {
          padding: 12px 16px;
          text-align: left;
          border-bottom: 1px solid #f3f4f6;
        }

        .documents-table th {
          background: #f9fafb;
          font-weight: 500;
          color: #6b7280;
          font-size: 13px;
          text-transform: uppercase;
        }

        .documents-table tbody tr {
          cursor: pointer;
          transition: background 0.15s;
        }

        .documents-table tbody tr:hover {
          background: #f9fafb;
        }

        .reference {
          font-weight: 500;
          color: #1f2937;
        }

        .type-badge {
          display: inline-block;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 500;
        }

        .type-badge.invoice {
          background: #dbeafe;
          color: #1e40af;
        }

        .type-badge.po {
          background: #fef3c7;
          color: #92400e;
        }

        .status-badge {
          display: inline-block;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 500;
        }

        .status-badge.new,
        .status-badge.open {
          background: #e0e7ff;
          color: #3730a3;
        }

        .status-badge.matched {
          background: #dcfce7;
          color: #166534;
        }

        .status-badge.needs-review {
          background: #fef3c7;
          color: #92400e;
        }

        .status-badge.exception {
          background: #fee2e2;
          color: #991b1b;
        }

        .status-badge.approved {
          background: #dcfce7;
          color: #166534;
        }

        .status-badge.rejected {
          background: #fee2e2;
          color: #991b1b;
        }

        .status-badge.routed {
          background: #e0e7ff;
          color: #3730a3;
        }

        .status-badge.closed {
          background: #f3f4f6;
          color: #6b7280;
        }
      `}</style>
    </div>
  );
}

