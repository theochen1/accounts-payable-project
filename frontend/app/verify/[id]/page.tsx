'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { documentApi, Document, InvoiceSaveData, POSaveData } from '@/lib/api';
import DocumentViewer from '@/components/verification/DocumentViewer';
import ExtractionForm from '@/components/verification/ExtractionForm';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import { useToast } from '@/components/ui/use-toast';
import Header from '@/components/layout/Header';

export default function VerifyPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const documentId = parseInt(params.id as string);

  const [document, setDocument] = useState<Document | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [documentUrl, setDocumentUrl] = useState<string>('');

  useEffect(() => {
    loadDocument();
  }, [documentId]);

  const loadDocument = async () => {
    try {
      const doc = await documentApi.get(documentId);
      setDocument(doc);
      
      // Construct document URL - Note: Backend needs to implement /api/documents/{id}/file endpoint
      // For now, we'll try to construct a URL but it may not work until endpoint is added
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      if (doc.storage_path) {
        // Try the file endpoint (may need to be implemented in backend)
        setDocumentUrl(`${baseUrl}/api/documents/${doc.id}/file`);
      }
    } catch (error: any) {
      toast({
        title: 'Failed to load document',
        description: error.message || 'Document not found.',
        variant: 'destructive',
      });
      router.push('/documents');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (data: InvoiceSaveData | POSaveData) => {
    if (!document) return;

    setSaving(true);
    try {
      await documentApi.save(document.id, {
        invoice_data: document.document_type === 'invoice' ? (data as InvoiceSaveData) : undefined,
        po_data: document.document_type === 'po' ? (data as POSaveData) : undefined,
      });

      toast({
        title: 'Document saved',
        description: 'The document has been processed and saved successfully.',
      });

      router.push('/processed');
    } catch (error: any) {
      toast({
        title: 'Failed to save',
        description: error.message || 'Failed to save document.',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    router.push('/documents');
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!document) {
    return null;
  }

  return (
    <div className="flex flex-col h-full">
      <Header
        title="Verify Document"
        description={`Review and verify extracted data for ${document.filename}`}
      />
      <div className="flex-1 overflow-hidden flex">
        {/* Left Pane - Document Viewer */}
        <div className="w-1/2 border-r border-border">
          {documentUrl ? (
            <DocumentViewer documentUrl={documentUrl} filename={document.filename} />
          ) : (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              Document preview not available
            </div>
          )}
        </div>

        {/* Right Pane - Extraction Form */}
        <div className="w-1/2 overflow-hidden">
          <ExtractionForm
            document={document}
            onSave={handleSave}
            onCancel={handleCancel}
            isSaving={saving}
          />
        </div>
      </div>
    </div>
  );
}

