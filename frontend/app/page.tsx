'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { documentApi, Document, pairsApi, DocumentPairSummary } from '@/lib/api';
import Header from '@/components/layout/Header';
import StatsCards from '@/components/dashboard/StatsCards';
import PendingDocuments from '@/components/dashboard/PendingDocuments';
import QuickUpload from '@/components/dashboard/QuickUpload';
import EmptyState from '@/components/shared/EmptyState';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import UploadModal from '@/components/documents/UploadModal';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Link2 } from 'lucide-react';
import Link from 'next/link';

export default function Dashboard() {
  const router = useRouter();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);

  useEffect(() => {
    loadDocuments();
  }, []);

  const [allDocuments, setAllDocuments] = useState<Document[]>([]);
  const [processedDocuments, setProcessedDocuments] = useState<number>(0);
  const [pairsStats, setPairsStats] = useState({
    total: 0,
    needsReview: 0,
    approvedToday: 0,
  });

  const loadDocuments = async () => {
    try {
      // Load all documents (including processed) for stats
      const allDocs = await documentApi.list();
      setAllDocuments(allDocs);
      
      // Filter out processed documents for the pending list (they're in the processed archive)
      setDocuments(allDocs.filter((d) => d.status !== 'processed'));
      
      // Load processed documents count separately
      const processedDocs = await documentApi.listProcessed();
      setProcessedDocuments(processedDocs.length);

      // Load pairs stats
      try {
        const allPairs = await pairsApi.list();
        const needsReviewPairs = await pairsApi.list({ status: ['needs_review'] });
        const approvedPairs = await pairsApi.list({ status: ['approved'] });
        
        // Count approved today (using updated_at as proxy since approved_at may not be in summary)
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const approvedToday = approvedPairs.filter(pair => {
          const updatedAt = new Date(pair.updated_at);
          return updatedAt >= today && pair.overall_status === 'approved';
        });

        setPairsStats({
          total: allPairs.length,
          needsReview: needsReviewPairs.length,
          approvedToday: approvedToday.length,
        });
      } catch (error) {
        console.error('Failed to load pairs stats:', error);
        // Set defaults on error
        setPairsStats({ total: 0, needsReview: 0, approvedToday: 0 });
      }
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const stats = {
    pending: allDocuments.filter((d) => d.status === 'pending' || d.status === 'uploaded' || d.status === 'classified' || d.status === 'pending_verification').length,
    processing: allDocuments.filter((d) => d.status === 'processing' || d.status === 'ocr_processing').length,
    processed: processedDocuments,
    errors: allDocuments.filter((d) => d.status === 'error').length,
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
          
          {/* Document Pairs Stats */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg font-semibold">Document Pairs</CardTitle>
                <Link 
                  href="/matching/pairs"
                  className="text-sm text-primary hover:underline"
                >
                  View All →
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-3">
                <div className="flex items-center gap-3">
                  <div className="rounded-full p-2 bg-blue-50">
                    <Link2 className="h-4 w-4 text-blue-600" />
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground">Total Pairs</div>
                    <div className="text-2xl font-bold">{pairsStats.total}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="rounded-full p-2 bg-amber-50">
                    <Link2 className="h-4 w-4 text-amber-600" />
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground">Needs Review</div>
                    <div className="text-2xl font-bold">{pairsStats.needsReview}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="rounded-full p-2 bg-green-50">
                    <Link2 className="h-4 w-4 text-green-600" />
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground">Approved Today</div>
                    <div className="text-2xl font-bold">{pairsStats.approvedToday}</div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
          
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
