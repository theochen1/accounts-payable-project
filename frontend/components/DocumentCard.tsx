'use client';

import { useState } from 'react';
import { Document } from '@/lib/api';

interface DocumentCardProps {
  document: Document;
  onTypeChange: (id: number, type: 'invoice' | 'po') => void;
  onProcess: (id: number) => void;
  onRetry: (id: number) => void;
  onDelete: (id: number) => void;
  isProcessing?: boolean;
}

export default function DocumentCard({
  document,
  onTypeChange,
  onProcess,
  onRetry,
  onDelete,
  isProcessing = false,
}: DocumentCardProps) {
  const [selectedType, setSelectedType] = useState<'invoice' | 'po' | ''>(
    document.document_type || ''
  );

  const handleTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newType = e.target.value as 'invoice' | 'po';
    setSelectedType(newType);
    if (newType) {
      onTypeChange(document.id, newType);
    }
  };

  const getStatusBadge = () => {
    switch (document.status) {
      case 'pending':
        return <span className="badge badge-pending">Pending</span>;
      case 'processing':
        return <span className="badge badge-processing">Processing...</span>;
      case 'processed':
        return <span className="badge badge-success">Processed</span>;
      case 'error':
        return <span className="badge badge-error">Error</span>;
      default:
        return null;
    }
  };

  const canProcess = document.status === 'pending' && document.document_type;
  const canRetry = document.status === 'error';
  const isReady = document.status === 'processed';

  return (
    <div className={`document-card ${document.status}`}>
      <div className="document-card-content">
        <div className="document-info">
          <div className="document-filename" title={document.filename}>
            {document.filename}
          </div>
          {getStatusBadge()}
        </div>

        {document.status === 'error' && document.error_message && (
          <div className="error-message" title={document.error_message}>
            {document.error_message.substring(0, 100)}
            {document.error_message.length > 100 ? '...' : ''}
          </div>
        )}

        <div className="document-actions">
          <select
            value={selectedType}
            onChange={handleTypeChange}
            disabled={document.status === 'processing' || isReady}
            className="type-select"
          >
            <option value="">Select type...</option>
            <option value="invoice">Invoice</option>
            <option value="po">Purchase Order</option>
          </select>

          {canProcess && (
            <button
              onClick={() => onProcess(document.id)}
              disabled={isProcessing}
              className="btn btn-primary"
            >
              {isProcessing ? 'Processing...' : 'Process'}
            </button>
          )}

          {canRetry && (
            <button
              onClick={() => onRetry(document.id)}
              disabled={isProcessing}
              className="btn btn-warning"
            >
              Retry
            </button>
          )}

          {document.status === 'processing' && (
            <div className="processing-spinner">
              <span className="spinner"></span>
            </div>
          )}

          <button
            onClick={() => onDelete(document.id)}
            disabled={document.status === 'processing'}
            className="btn btn-delete"
            title="Delete"
          >
            ×
          </button>
        </div>
      </div>

      <style jsx>{`
        .document-card {
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          padding: 16px;
          margin-bottom: 12px;
          transition: all 0.2s;
        }

        .document-card:hover {
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }

        .document-card.processing {
          background: #f0f9ff;
          border-color: #3b82f6;
        }

        .document-card.error {
          background: #fef2f2;
          border-color: #ef4444;
        }

        .document-card.processed {
          background: #f0fdf4;
          border-color: #22c55e;
        }

        .document-card-content {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .document-info {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .document-filename {
          font-weight: 500;
          color: #1f2937;
          flex: 1;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .badge {
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 500;
        }

        .badge-pending {
          background: #fef3c7;
          color: #92400e;
        }

        .badge-processing {
          background: #dbeafe;
          color: #1e40af;
        }

        .badge-success {
          background: #dcfce7;
          color: #166534;
        }

        .badge-error {
          background: #fee2e2;
          color: #991b1b;
        }

        .error-message {
          font-size: 13px;
          color: #dc2626;
          background: #fef2f2;
          padding: 8px 12px;
          border-radius: 4px;
        }

        .document-actions {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-wrap: wrap;
        }

        .type-select {
          padding: 8px 12px;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          font-size: 14px;
          min-width: 150px;
        }

        .type-select:disabled {
          background: #f3f4f6;
          cursor: not-allowed;
        }

        .btn {
          padding: 8px 16px;
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

        .btn-warning {
          background: #f59e0b;
          color: white;
        }

        .btn-warning:hover:not(:disabled) {
          background: #d97706;
        }

        .btn-delete {
          background: transparent;
          color: #6b7280;
          font-size: 20px;
          padding: 4px 8px;
          line-height: 1;
        }

        .btn-delete:hover:not(:disabled) {
          color: #dc2626;
          background: #fee2e2;
        }

        .processing-spinner {
          display: flex;
          align-items: center;
        }

        .spinner {
          width: 20px;
          height: 20px;
          border: 2px solid #e5e7eb;
          border-top-color: #3b82f6;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  );
}

