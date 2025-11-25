'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { poApi, POList } from '@/lib/api';
import Link from 'next/link';

export default function PurchaseOrdersPage() {
  const [pos, setPos] = useState<POList[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const router = useRouter();

  useEffect(() => {
    loadPOs();
  }, [statusFilter]);

  const loadPOs = async () => {
    try {
      setLoading(true);
      const params: any = {};
      if (statusFilter) {
        params.status = statusFilter;
      }
      const data = await poApi.list(params);
      setPos(data);
    } catch (error) {
      console.error('Failed to load purchase orders:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRowClick = (poNumber: string) => {
    router.push(`/purchase-orders/${poNumber}`);
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

  const getStatusClass = (status: string) => {
    return `status-badge status-${status}`;
  };

  return (
    <div className="container">
      <div className="header">
        <h1>Purchase Orders</h1>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <Link href="/" className="button" style={{ textDecoration: 'none' }}>
            Invoices
          </Link>
          <Link href="/purchase-orders/new" className="button button-primary" style={{ textDecoration: 'none' }}>
            Create PO
          </Link>
        </div>
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
            <option value="open">Open</option>
            <option value="partially_received">Partially Received</option>
            <option value="closed">Closed</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div>Loading...</div>
      ) : pos.length === 0 ? (
        <div className="card">
          <p>No purchase orders found.</p>
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>PO Number</th>
              <th>Vendor</th>
              <th>Total</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {pos.map((po) => (
              <tr key={po.id} onClick={() => handleRowClick(po.po_number)} style={{ cursor: 'pointer' }}>
                <td>{po.po_number}</td>
                <td>{po.vendor_name || 'N/A'}</td>
                <td>{formatCurrency(po.total_amount, po.currency)}</td>
                <td>
                  <span className={getStatusClass(po.status)}>
                    {po.status.replace('_', ' ').toUpperCase()}
                  </span>
                </td>
                <td>{formatDate(po.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

