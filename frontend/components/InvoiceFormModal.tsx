'use client';

import { useState, useEffect } from 'react';
import { Document, InvoiceSaveData, vendorApi } from '@/lib/api';

interface Vendor {
  id: number;
  name: string;
}

interface InvoiceFormModalProps {
  document: Document;
  onSave: (data: InvoiceSaveData) => void;
  onCancel: () => void;
  isSaving?: boolean;
}

export default function InvoiceFormModal({
  document,
  onSave,
  onCancel,
  isSaving = false,
}: InvoiceFormModalProps) {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const ocrData = document.ocr_data || {};

  const [formData, setFormData] = useState<InvoiceSaveData>({
    invoice_number: ocrData.invoice_number || '',
    vendor_name: ocrData.vendor_name || '',
    vendor_id: undefined,
    po_number: ocrData.po_number || '',
    invoice_date: ocrData.invoice_date || '',
    total_amount: ocrData.total_amount || undefined,
    currency: ocrData.currency || 'USD',
    line_items: ocrData.line_items || [],
  });

  useEffect(() => {
    loadVendors();
  }, []);

  const loadVendors = async () => {
    try {
      const data = await vendorApi.list();
      setVendors(data);
      
      // Try to match vendor by name
      if (formData.vendor_name && !formData.vendor_id) {
        const matchedVendor = data.find(
          (v: Vendor) => v.name.toLowerCase() === formData.vendor_name?.toLowerCase()
        );
        if (matchedVendor) {
          setFormData(prev => ({ ...prev, vendor_id: matchedVendor.id }));
        }
      }
    } catch (error) {
      console.error('Failed to load vendors:', error);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.invoice_number) {
      alert('Invoice number is required');
      return;
    }
    onSave(formData);
  };

  const handleInputChange = (field: keyof InvoiceSaveData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleVendorChange = (vendorId: string) => {
    if (vendorId) {
      const vendor = vendors.find(v => v.id === parseInt(vendorId));
      setFormData(prev => ({
        ...prev,
        vendor_id: parseInt(vendorId),
        vendor_name: vendor?.name || prev.vendor_name,
      }));
    } else {
      setFormData(prev => ({ ...prev, vendor_id: undefined }));
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal">
        <div className="modal-header">
          <h2>Review Invoice Data</h2>
          <p className="modal-subtitle">
            Review and edit the extracted data before saving
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="invoice_number">Invoice Number *</label>
              <input
                type="text"
                id="invoice_number"
                value={formData.invoice_number}
                onChange={(e) => handleInputChange('invoice_number', e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="vendor">Vendor</label>
              <select
                id="vendor"
                value={formData.vendor_id || ''}
                onChange={(e) => handleVendorChange(e.target.value)}
              >
                <option value="">Select or create new...</option>
                {vendors.map((vendor) => (
                  <option key={vendor.id} value={vendor.id}>
                    {vendor.name}
                  </option>
                ))}
              </select>
              {!formData.vendor_id && formData.vendor_name && (
                <p className="field-hint">
                  New vendor will be created: {formData.vendor_name}
                </p>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="vendor_name">Vendor Name (from OCR)</label>
              <input
                type="text"
                id="vendor_name"
                value={formData.vendor_name || ''}
                onChange={(e) => handleInputChange('vendor_name', e.target.value)}
                placeholder="Enter vendor name"
              />
            </div>

            <div className="form-group">
              <label htmlFor="po_number">PO Number</label>
              <input
                type="text"
                id="po_number"
                value={formData.po_number || ''}
                onChange={(e) => handleInputChange('po_number', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="invoice_date">Invoice Date</label>
              <input
                type="date"
                id="invoice_date"
                value={formData.invoice_date || ''}
                onChange={(e) => handleInputChange('invoice_date', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="total_amount">Total Amount</label>
              <input
                type="number"
                id="total_amount"
                step="0.01"
                value={formData.total_amount || ''}
                onChange={(e) => handleInputChange('total_amount', e.target.value ? parseFloat(e.target.value) : undefined)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="currency">Currency</label>
              <select
                id="currency"
                value={formData.currency}
                onChange={(e) => handleInputChange('currency', e.target.value)}
              >
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="GBP">GBP</option>
                <option value="CAD">CAD</option>
                <option value="AUD">AUD</option>
              </select>
            </div>
          </div>

          {formData.line_items && formData.line_items.length > 0 && (
            <div className="line-items-section">
              <h3>Line Items</h3>
              <table className="line-items-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>SKU</th>
                    <th>Description</th>
                    <th>Qty</th>
                    <th>Unit Price</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {formData.line_items.map((item, index) => (
                    <tr key={index}>
                      <td>{item.line_no || index + 1}</td>
                      <td>{item.sku || '-'}</td>
                      <td>{item.description}</td>
                      <td>{item.quantity}</td>
                      <td>${item.unit_price?.toFixed(2)}</td>
                      <td>${(item.quantity * item.unit_price).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="modal-actions">
            <button
              type="button"
              onClick={onCancel}
              disabled={isSaving}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="btn btn-primary"
            >
              {isSaving ? 'Saving...' : 'Save Invoice'}
            </button>
          </div>
        </form>
      </div>

      <style jsx>{`
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          padding: 20px;
        }

        .modal {
          background: white;
          border-radius: 12px;
          max-width: 800px;
          width: 100%;
          max-height: 90vh;
          overflow-y: auto;
          padding: 24px;
        }

        .modal-header {
          margin-bottom: 24px;
        }

        .modal-header h2 {
          margin: 0 0 8px 0;
          font-size: 24px;
          color: #1f2937;
        }

        .modal-subtitle {
          color: #6b7280;
          margin: 0;
        }

        .form-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 16px;
          margin-bottom: 24px;
        }

        .form-group {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .form-group label {
          font-weight: 500;
          color: #374151;
          font-size: 14px;
        }

        .form-group input,
        .form-group select {
          padding: 10px 12px;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          font-size: 14px;
        }

        .form-group input:focus,
        .form-group select:focus {
          outline: none;
          border-color: #3b82f6;
          box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }

        .field-hint {
          font-size: 12px;
          color: #059669;
          margin: 4px 0 0 0;
        }

        .line-items-section {
          margin-bottom: 24px;
        }

        .line-items-section h3 {
          font-size: 16px;
          color: #1f2937;
          margin: 0 0 12px 0;
        }

        .line-items-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 14px;
        }

        .line-items-table th,
        .line-items-table td {
          padding: 10px 12px;
          text-align: left;
          border-bottom: 1px solid #e5e7eb;
        }

        .line-items-table th {
          background: #f9fafb;
          font-weight: 500;
          color: #6b7280;
        }

        .modal-actions {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
          padding-top: 16px;
          border-top: 1px solid #e5e7eb;
        }

        .btn {
          padding: 10px 20px;
          border: none;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
        }

        .btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .btn-primary {
          background: #3b82f6;
          color: white;
        }

        .btn-primary:hover:not(:disabled) {
          background: #2563eb;
        }

        .btn-secondary {
          background: #f3f4f6;
          color: #374151;
        }

        .btn-secondary:hover:not(:disabled) {
          background: #e5e7eb;
        }

        @media (max-width: 640px) {
          .form-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
}

