'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { documentApi, Document } from '@/lib/api';
import Header from '@/components/layout/Header';
import DocumentCard from '@/components/documents/DocumentCard';
import UploadModal from '@/components/documents/UploadModal';
import EmptyState from '@/components/shared/EmptyState';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import { useToast } from '@/components/ui/use-toast';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function DocumentsPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [processingIds, setProcessingIds] = useState<Set<number>>(new Set());
  const [statusFilter, setStatusFilter] = useState<string>('all');

  useEffect(() => {
    loadDocuments();
  }, []);

  // Poll for processing documents
  useEffect(() => {
    const hasProcessing = documents.some((d) => d.status === 'processing');
    if (!hasProcessing) return;

    const interval = setInterval(() => {
      loadDocuments();
    }, 3000);

    return () => clearInterval(interval);
  }, [documents]);

  const loadDocuments = async () => {
    try {
      const docs = await documentApi.list();
      // Filter out processed documents (they're in the processed archive)
      setDocuments(docs.filter((d) => d.status !== 'processed'));
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTypeChange = async (id: number, type: 'invoice' | 'purchase_order' | 'receipt') => {
    try {
      await documentApi.setType(id, type);
      await loadDocuments();
    } catch (error: any) {
      toast({
        title: 'Failed to set document type',
        description: error.message || 'Please try again.',
        variant: 'destructive',
      });
    }
  };

  const handleProcess = async (id: number) => {
    setProcessingIds((prev) => new Set(prev).add(id));

    try {
      const result = await documentApi.process(id);
      await loadDocuments();

      if (result.status === 'pending_verification') {
        toast({
          title: 'Processing complete',
          description: 'Document has been processed successfully.',
        });
        // Auto-navigate to verification after a short delay
        setTimeout(() => {
          router.push(`/verify/${id}`);
        }, 1000);
      }
    } catch (error: any) {
      toast({
        title: 'Processing failed',
        description: error.message || 'Failed to process document.',
        variant: 'destructive',
      });
      await loadDocuments();
    } finally {
      setProcessingIds((prev) => {
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
      toast({
        title: 'Document deleted',
        description: 'The document has been removed.',
      });
    } catch (error: any) {
      toast({
        title: 'Failed to delete',
        description: error.message || 'Please try again.',
        variant: 'destructive',
      });
    }
  };

  const handleUploadSuccess = () => {
    setUploadModalOpen(false);
    loadDocuments();
  };

  const filteredDocuments =
    statusFilter === 'all'
      ? documents
      : documents.filter((d) => d.status === statusFilter);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <Header
        title="Document Queue"
        description="Upload and process documents with OCR"
        action={{
          label: 'Upload Document',
          onClick: () => setUploadModalOpen(true),
        }}
      />
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-7xl mx-auto space-y-6">
          <Tabs value={statusFilter} onValueChange={setStatusFilter}>
            <TabsList>
              <TabsTrigger value="all">All ({documents.length})</TabsTrigger>
              <TabsTrigger value="pending">
                Pending ({documents.filter((d) => d.status === 'pending').length})
              </TabsTrigger>
              <TabsTrigger value="processing">
                Processing ({documents.filter((d) => d.status === 'processing').length})
              </TabsTrigger>
              <TabsTrigger value="processed">
                Processed ({documents.filter((d) => d.status === 'processed').length})
              </TabsTrigger>
              <TabsTrigger value="error">
                Errors ({documents.filter((d) => d.status === 'error').length})
              </TabsTrigger>
            </TabsList>
          </Tabs>

          {filteredDocuments.length === 0 ? (
            <EmptyState
              title="No documents"
              description={
                statusFilter === 'all'
                  ? 'Upload a document to get started with processing.'
                  : `No documents with status "${statusFilter}".`
              }
              action={
                statusFilter === 'all'
                  ? {
                      label: 'Upload Document',
                      onClick: () => setUploadModalOpen(true),
                    }
                  : undefined
              }
            />
          ) : (
            <div className="space-y-4">
              {filteredDocuments.map((doc) => (
                <DocumentCard
                  key={doc.id}
                  document={doc}
                  onTypeChange={handleTypeChange}
                  onProcess={handleProcess}
                  onRetry={handleRetry}
                  onDelete={handleDelete}
                  isProcessing={processingIds.has(doc.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      <UploadModal
        open={uploadModalOpen}
        onOpenChange={setUploadModalOpen}
        onSuccess={handleUploadSuccess}
      />
    </div>
  );
}

