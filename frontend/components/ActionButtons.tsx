'use client';

import { useState } from 'react';
import { InvoiceDetail } from '@/lib/api';

interface ActionButtonsProps {
  invoice: InvoiceDetail;
  onAction: (action: 'approve' | 'reject' | 'route', reason?: string) => void;
}

export default function ActionButtons({ invoice, onAction }: ActionButtonsProps) {
  const [showReject, setShowReject] = useState(false);
  const [showRoute, setShowRoute] = useState(false);
  const [reason, setReason] = useState('');

  const canApprove = ['matched', 'needs_review'].includes(invoice.status);
  const canReject = !['approved', 'rejected'].includes(invoice.status);
  const canRoute = !['approved', 'rejected', 'routed'].includes(invoice.status);

  const handleApprove = () => {
    if (confirm('Are you sure you want to approve this invoice?')) {
      onAction('approve');
    }
  };

  const handleReject = () => {
    if (!reason.trim()) {
      alert('Please provide a reason for rejection');
      return;
    }
    if (confirm('Are you sure you want to reject this invoice?')) {
      onAction('reject', reason);
      setShowReject(false);
      setReason('');
    }
  };

  const handleRoute = () => {
    if (!reason.trim()) {
      alert('Please provide a routing target/reason');
      return;
    }
    if (confirm('Are you sure you want to route this invoice?')) {
      onAction('route', reason);
      setShowRoute(false);
      setReason('');
    }
  };

  return (
    <div className="card">
      <h2>Actions</h2>
      
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '20px' }}>
        {canApprove && (
          <button onClick={handleApprove} className="button button-success">
            Approve Invoice
          </button>
        )}
        {canReject && (
          <button onClick={() => setShowReject(!showReject)} className="button button-danger">
            Reject Invoice
          </button>
        )}
        {canRoute && (
          <button onClick={() => setShowRoute(!showRoute)} className="button button-secondary">
            Route Invoice
          </button>
        )}
      </div>

      {showReject && (
        <div className="form-group">
          <label>Reason for Rejection *</label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Enter reason for rejection..."
          />
          <div style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
            <button onClick={handleReject} className="button button-danger">
              Confirm Reject
            </button>
            <button onClick={() => { setShowReject(false); setReason(''); }} className="button button-secondary">
              Cancel
            </button>
          </div>
        </div>
      )}

      {showRoute && (
        <div className="form-group">
          <label>Routing Target/Reason *</label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Enter routing target or reason..."
          />
          <div style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
            <button onClick={handleRoute} className="button button-secondary">
              Confirm Route
            </button>
            <button onClick={() => { setShowRoute(false); setReason(''); }} className="button button-secondary">
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

