'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { poApi, vendorApi, POCreate, POLineCreate } from '@/lib/api';
import Link from 'next/link';

export default function CreatePOPage() {
  const [vendors, setVendors] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<Omit<POCreate, 'po_lines'>>({
    po_number: '',
    vendor_id: 0,
    currency: 'USD',
    status: 'open',
    requester_email: '',
  });
  const [poLines, setPoLines] = useState<POLineCreate[]>([
    { line_no: 1, description: '', quantity: 0, unit_price: 0 }
  ]);
  const router = useRouter();

  useEffect(() => {
    loadVendors();
  }, []);

  const loadVendors = async () => {
    try {
      const data = await vendorApi.list();
      setVendors(data);
    } catch (error) {
      console.error('Failed to load vendors:', error);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.po_number || formData.vendor_id === 0) {
      alert('Please fill in PO number and select a vendor');
      return;
    }

    if (poLines.length === 0 || poLines.some(line => !line.description || line.quantity <= 0 || line.unit_price <= 0)) {
      alert('Please add at least one valid line item');
      return;
    }

    try {
      setLoading(true);
      const po: POCreate = {
        ...formData,
        po_lines: poLines,
      };
      await poApi.create(po);
      router.push('/purchase-orders');
    } catch (error: any) {
      alert(`Failed to create purchase order: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const addLineItem = () => {
    setPoLines([...poLines, {
      line_no: poLines.length + 1,
      description: '',
      quantity: 0,
      unit_price: 0
    }]);
  };

  const removeLineItem = (index: number) => {
    const newLines = poLines.filter((_, i) => i !== index);
    // Renumber lines
    newLines.forEach((line, i) => {
      line.line_no = i + 1;
    });
    setPoLines(newLines);
  };

  const updateLineItem = (index: number, field: keyof POLineCreate, value: any) => {
    const newLines = [...poLines];
    newLines[index] = { ...newLines[index], [field]: value };
    setPoLines(newLines);
  };

  const calculateTotal = () => {
    return poLines.reduce((sum, line) => sum + (line.quantity * line.unit_price), 0);
  };

  return (
    <div className="container">
      <div className="header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1>Create Purchase Order</h1>
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

      <form onSubmit={handleSubmit} className="card">
        <h2>PO Information</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px', marginBottom: '20px' }}>
          <div className="form-group">
            <label htmlFor="po_number">PO Number *</label>
            <input
              id="po_number"
              type="text"
              value={formData.po_number}
              onChange={(e) => setFormData({ ...formData, po_number: e.target.value })}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="vendor_id">Vendor *</label>
            <select
              id="vendor_id"
              value={formData.vendor_id}
              onChange={(e) => setFormData({ ...formData, vendor_id: parseInt(e.target.value) })}
              required
            >
              <option value="0">Select a vendor</option>
              {vendors.map((vendor) => (
                <option key={vendor.id} value={vendor.id}>
                  {vendor.name}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="currency">Currency</label>
            <select
              id="currency"
              value={formData.currency}
              onChange={(e) => setFormData({ ...formData, currency: e.target.value })}
            >
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
              <option value="GBP">GBP</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="status">Status</label>
            <select
              id="status"
              value={formData.status}
              onChange={(e) => setFormData({ ...formData, status: e.target.value })}
            >
              <option value="open">Open</option>
              <option value="partially_received">Partially Received</option>
              <option value="closed">Closed</option>
            </select>
          </div>
          <div className="form-group" style={{ gridColumn: 'span 2' }}>
            <label htmlFor="requester_email">Requester Email</label>
            <input
              id="requester_email"
              type="email"
              value={formData.requester_email}
              onChange={(e) => setFormData({ ...formData, requester_email: e.target.value })}
            />
          </div>
        </div>

        <div style={{ marginTop: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3>Line Items</h3>
            <button type="button" onClick={addLineItem} className="button button-primary">
              Add Line Item
            </button>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Line</th>
                <th>SKU</th>
                <th>Description *</th>
                <th>Quantity *</th>
                <th>Unit Price *</th>
                <th>Total</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {poLines.map((line, index) => (
                <tr key={index}>
                  <td>{line.line_no}</td>
                  <td>
                    <input
                      type="text"
                      value={line.sku || ''}
                      onChange={(e) => updateLineItem(index, 'sku', e.target.value)}
                      style={{ width: '100px' }}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={line.description}
                      onChange={(e) => updateLineItem(index, 'description', e.target.value)}
                      required
                      style={{ width: '200px' }}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.01"
                      value={line.quantity}
                      onChange={(e) => updateLineItem(index, 'quantity', parseFloat(e.target.value) || 0)}
                      required
                      min="0"
                      style={{ width: '100px' }}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.01"
                      value={line.unit_price}
                      onChange={(e) => updateLineItem(index, 'unit_price', parseFloat(e.target.value) || 0)}
                      required
                      min="0"
                      style={{ width: '100px' }}
                    />
                  </td>
                  <td>
                    {new Intl.NumberFormat('en-US', {
                      style: 'currency',
                      currency: formData.currency || 'USD',
                    }).format(line.quantity * line.unit_price)}
                  </td>
                  <td>
                    {poLines.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeLineItem(index)}
                        className="button"
                        style={{ padding: '4px 8px' }}
                      >
                        Remove
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={5} style={{ textAlign: 'right', fontWeight: 'bold' }}>Total:</td>
                <td style={{ fontWeight: 'bold' }}>
                  {new Intl.NumberFormat('en-US', {
                    style: 'currency',
                    currency: formData.currency || 'USD',
                  }).format(calculateTotal())}
                </td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>

        <div style={{ marginTop: '20px', display: 'flex', gap: '16px', justifyContent: 'flex-end' }}>
          <Link href="/purchase-orders" className="button" style={{ textDecoration: 'none' }}>
            Cancel
          </Link>
          <button type="submit" className="button button-primary" disabled={loading}>
            {loading ? 'Creating...' : 'Create PO'}
          </button>
        </div>
      </form>
    </div>
  );
}

