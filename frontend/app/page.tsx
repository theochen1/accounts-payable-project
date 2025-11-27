'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  documentApi,
  Document,
  ProcessedDocument,
  InvoiceSaveData,
  POSaveData,
} from '@/lib/api';
import DocumentCard from '@/components/DocumentCard';
import ProcessedDocuments from '@/components/ProcessedDocuments';
import InvoiceFormModal from '@/components/InvoiceFormModal';
import POFormModal from '@/components/POFormModal';

export default function Home() {
  // Document queue state
  const [documents, setDocuments] = useState<Document[]>([]);
  const [processedDocs, setProcessedDocs] = useState<ProcessedDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [processingIds, setProcessingIds] = useState<Set<number>>(new Set());

  // Modal state
  const [activeDocument, setActiveDocument] = useState<Document | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Load documents on mount
  useEffect(() => {
    loadAll();
  }, []);

  // Poll for processing documents
  useEffect(() => {
    const hasProcessing = documents.some(d => d.status === 'processing');
    if (!hasProcessing) return;

    const interval = setInterval(() => {
      loadDocuments();
    }, 3000);

    return () => clearInterval(interval);
  }, [documents]);

  const loadAll = async () => {
    setLoading(true);
    await Promise.all([loadDocuments(), loadProcessedDocuments()]);
    setLoading(false);
  };

  const loadDocuments = async () => {
    try {
      const docs = await documentApi.list();
      // Only show unprocessed documents (pending, processing, processed, error)
      // Hide documents that have been saved (processed_id is set)
      const queueDocs = docs.filter(d => !d.processed_id);
      setDocuments(queueDocs);
    } catch (error) {
      console.error('Failed to load documents:', error);
    }
  };

  const loadProcessedDocuments = async () => {
    try {
      const docs = await documentApi.listProcessed();
      setProcessedDocs(docs);
    } catch (error) {
      console.error('Failed to load processed documents:', error);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      await documentApi.upload(file);
      await loadDocuments();
    } catch (error: any) {
      alert(`Failed to upload document: ${error.message}`);
    }
    
    // Reset file input
    event.target.value = '';
  };

  const handleTypeChange = async (id: number, type: 'invoice' | 'po') => {
    try {
      await documentApi.setType(id, type);
      await loadDocuments();
    } catch (error: any) {
      alert(`Failed to set document type: ${error.message}`);
    }
  };

  const handleProcess = async (id: number) => {
    setProcessingIds(prev => new Set(prev).add(id));
    
    try {
      const result = await documentApi.process(id);
      await loadDocuments();
      
      // If processing succeeded, open the form modal
      if (result.status === 'processed') {
        const doc = await documentApi.get(id);
        setActiveDocument(doc);
      }
    } catch (error: any) {
      alert(`Processing failed: ${error.message}`);
      await loadDocuments();
    } finally {
      setProcessingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(id);
        return newSet;
      });
    }
  };

  const handleRetry = async (id: number) => {
    await handleProcess(id);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
      await documentApi.delete(id);
      await loadDocuments();
    } catch (error: any) {
      alert(`Failed to delete document: ${error.message}`);
    }
  };

  const handleSaveInvoice = async (data: InvoiceSaveData) => {
    if (!activeDocument) return;

    setIsSaving(true);
    try {
      await documentApi.save(activeDocument.id, { invoice_data: data });
      setActiveDocument(null);
      await loadAll();
    } catch (error: any) {
      alert(`Failed to save invoice: ${error.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleSavePO = async (data: POSaveData) => {
    if (!activeDocument) return;

    setIsSaving(true);
    try {
      await documentApi.save(activeDocument.id, { po_data: data });
      setActiveDocument(null);
      await loadAll();
    } catch (error: any) {
      alert(`Failed to save purchase order: ${error.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancelModal = () => {
    setActiveDocument(null);
  };

  // Open form for already-processed documents
  const openFormForDocument = async (doc: Document) => {
    if (doc.status === 'processed' && !doc.processed_id) {
      setActiveDocument(doc);
    }
  };

  return (
    <div className="container">
      <div className="header">
        <h1>Accounts Payable Platform</h1>
        <p className="subtitle">Upload documents, process with OCR, and manage invoices & purchase orders</p>
      </div>

      {/* Upload Section */}
      <div className="upload-section">
        <label htmlFor="file-upload" className="upload-button">
          <span className="upload-icon">+</span>
          Upload Document (PDF/Image)
        </label>
        <input
          id="file-upload"
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.gif,.bmp,.webp,.tiff,.tif"
          onChange={handleFileUpload}
          style={{ display: 'none' }}
        />
      </div>

      {/* Document Queue */}
      <div className="queue-section">
        <h2>Document Queue</h2>
        {loading ? (
          <div className="loading">Loading...</div>
        ) : documents.length === 0 ? (
          <div className="empty-state">
            No documents in queue. Upload a document to get started.
          </div>
        ) : (
          <div className="document-list">
            {documents.map(doc => (
              <div key={doc.id} onClick={() => openFormForDocument(doc)}>
                <DocumentCard
                  document={doc}
                  onTypeChange={handleTypeChange}
                  onProcess={handleProcess}
                  onRetry={handleRetry}
                  onDelete={handleDelete}
                  isProcessing={processingIds.has(doc.id)}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Processed Documents */}
      <div className="processed-section">
        <ProcessedDocuments
          documents={processedDocs}
          loading={loading}
        />
      </div>

      {/* Form Modals */}
      {activeDocument && activeDocument.document_type === 'invoice' && (
        <InvoiceFormModal
          document={activeDocument}
          onSave={handleSaveInvoice}
          onCancel={handleCancelModal}
          isSaving={isSaving}
        />
      )}

      {activeDocument && activeDocument.document_type === 'po' && (
        <POFormModal
          document={activeDocument}
          onSave={handleSavePO}
          onCancel={handleCancelModal}
          isSaving={isSaving}
        />
      )}

      <style jsx>{`
        .container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 32px 24px;
        }

        .header {
          margin-bottom: 32px;
        }

        .header h1 {
          margin: 0 0 8px 0;
          font-size: 32px;
          color: #1f2937;
        }

        .subtitle {
          color: #6b7280;
          margin: 0;
        }

        .upload-section {
          margin-bottom: 32px;
        }

        .upload-button {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 14px 24px;
          background: linear-gradient(135deg, #3b82f6, #2563eb);
          color: white;
          border-radius: 8px;
          font-size: 16px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
          box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
        }

        .upload-button:hover {
          background: linear-gradient(135deg, #2563eb, #1d4ed8);
          box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
          transform: translateY(-1px);
        }

        .upload-icon {
          font-size: 20px;
          font-weight: bold;
        }

        .queue-section {
          margin-bottom: 40px;
        }

        .queue-section h2 {
          font-size: 20px;
          color: #1f2937;
          margin: 0 0 16px 0;
        }

        .loading {
          padding: 24px;
          text-align: center;
          color: #6b7280;
        }

        .empty-state {
          padding: 40px;
          text-align: center;
          color: #6b7280;
          background: #f9fafb;
          border-radius: 8px;
          border: 2px dashed #e5e7eb;
        }

        .document-list {
          display: flex;
          flex-direction: column;
        }

        .processed-section {
          margin-top: 24px;
        }
      `}</style>
    </div>
  );
}
