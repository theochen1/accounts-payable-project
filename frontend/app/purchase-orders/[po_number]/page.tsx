'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { poApi, PurchaseOrder } from '@/lib/api';
import Link from 'next/link';

export default function PODetailPage() {
  const [po, setPo] = useState<PurchaseOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const params = useParams();
  const poNumber = params?.po_number as string;

  useEffect(() => {
    if (poNumber) {
      loadPO();
    }
  }, [poNumber]);

  const loadPO = async () => {
    try {
      setLoading(true);
      const data = await poApi.get(poNumber);
      setPo(data);
    } catch (error: any) {
      console.error('Failed to load purchase order:', error);
      alert(`Failed to load purchase order: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number | undefined, currency: string) => {
    if (amount === undefined || amount === null) return 'N/A';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
    }).format(amount);
  };

  const formatDate = (dateString: string | undefined) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusClass = (status: string) => {
    return `status-badge status-${status}`;
  };

  if (loading) {
    return <div className="container">Loading...</div>;
  }

  if (!po) {
    return <div className="container">Purchase order not found</div>;
  }

  return (
    <div className="container">
      <div className="header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1>Purchase Order Details</h1>
          <div style={{ display: 'flex', gap: '16px' }}>
            <Link href="/purchase-orders" className="button" style={{ textDecoration: 'none' }}>
              Back to POs
            </Link>
            <Link href="/" className="button" style={{ textDecoration: 'none' }}>
              Invoices
            </Link>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>PO Information</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
          <div className="form-group">
            <label>PO Number</label>
            <div>{po.po_number}</div>
          </div>
          <div className="form-group">
            <label>Status</label>
            <div>
              <span className={getStatusClass(po.status)}>
                {po.status.replace('_', ' ').toUpperCase()}
              </span>
            </div>
          </div>
          <div className="form-group">
            <label>Vendor</label>
            <div>{po.vendor_name || 'N/A'}</div>
          </div>
          <div className="form-group">
            <label>Total Amount</label>
            <div>{formatCurrency(po.total_amount, po.currency)}</div>
          </div>
          <div className="form-group">
            <label>Currency</label>
            <div>{po.currency}</div>
          </div>
          <div className="form-group">
            <label>Requester Email</label>
            <div>{po.requester_email || 'N/A'}</div>
          </div>
          <div className="form-group">
            <label>Created</label>
            <div>{formatDate(po.created_at)}</div>
          </div>
          <div className="form-group">
            <label>Updated</label>
            <div>{formatDate(po.updated_at)}</div>
          </div>
        </div>

        {po.po_lines && po.po_lines.length > 0 && (
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
                {po.po_lines.map((line) => (
                  <tr key={line.id}>
                    <td>{line.line_no}</td>
                    <td>{line.sku || 'N/A'}</td>
                    <td>{line.description}</td>
                    <td>{line.quantity}</td>
                    <td>{formatCurrency(line.unit_price, po.currency)}</td>
                    <td>{formatCurrency(line.quantity * line.unit_price, po.currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

