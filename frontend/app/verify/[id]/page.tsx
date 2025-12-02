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
      
      // Construct document URL using the file endpoint
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      if (doc.file_path) {
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
      // Format data according to DocumentVerify schema
      const isInvoice = document.document_type === 'invoice';
      
      if (isInvoice) {
        const invoiceData = data as InvoiceSaveData;
        await documentApi.save(document.id, {
          vendor_name: invoiceData.vendor_name,
          vendor_id: invoiceData.vendor_id,
          document_number: invoiceData.invoice_number,
          document_date: invoiceData.invoice_date,
          total_amount: invoiceData.total_amount,
          currency: invoiceData.currency || 'USD',
          line_items: invoiceData.line_items || [],
          invoice_data: invoiceData.po_number ? {
            po_number: invoiceData.po_number,
          } : undefined,
        });
      } else {
        const poData = data as POSaveData;
        await documentApi.save(document.id, {
          vendor_name: poData.vendor_name,
          vendor_id: poData.vendor_id,
          document_number: poData.po_number,
          document_date: poData.order_date,
          total_amount: poData.total_amount,
          currency: poData.currency || 'USD',
          line_items: poData.po_lines || [],
          po_data: poData.requester_email ? {
            requester_email: poData.requester_email,
          } : undefined,
        });
      }

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

