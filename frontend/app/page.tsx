'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { documentApi, Document } from '@/lib/api';
import Header from '@/components/layout/Header';
import StatsCards from '@/components/dashboard/StatsCards';
import PendingDocuments from '@/components/dashboard/PendingDocuments';
import QuickUpload from '@/components/dashboard/QuickUpload';
import EmptyState from '@/components/shared/EmptyState';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import UploadModal from '@/components/documents/UploadModal';

export default function Dashboard() {
  const router = useRouter();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const docs = await documentApi.list();
      setDocuments(docs.filter((d) => !d.processed_id));
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const stats = {
    pending: documents.filter((d) => d.status === 'pending').length,
    processing: documents.filter((d) => d.status === 'processing').length,
    processed: documents.filter((d) => d.status === 'processed').length,
    errors: documents.filter((d) => d.status === 'error').length,
  };

  const handleUploadSuccess = () => {
    setUploadModalOpen(false);
    loadDocuments();
    router.push('/documents');
  };

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
        title="Dashboard"
        description="Overview of your document processing pipeline"
        action={{
          label: 'Upload Document',
          onClick: () => setUploadModalOpen(true),
        }}
      />
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-7xl mx-auto space-y-8">
          <StatsCards {...stats} />
          
          {documents.length === 0 ? (
            <QuickUpload onUpload={() => setUploadModalOpen(true)} />
          ) : (
            <div className="grid gap-8 lg:grid-cols-2">
              <PendingDocuments
                documents={documents}
                onViewAll={() => router.push('/documents')}
              />
              <QuickUpload onUpload={() => setUploadModalOpen(true)} />
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
