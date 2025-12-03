'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  pairsApi,
  DocumentPairDetail,
  LineItemComparison,
  TimelineEntry,
} from '@/lib/api';
import { WorkflowStepper } from '@/components/matching/WorkflowStepper';
import { MatchSummaryCard } from '@/components/matching/MatchSummaryCard';
import { IssuesList } from '@/components/matching/IssuesList';
import { AIReasoningCard } from '@/components/matching/AIReasoningCard';
import { ApprovalActions } from '@/components/matching/ApprovalActions';
import { LineItemRow } from '@/components/matching/LineItemRow';
import { TimelineEvent } from '@/components/matching/TimelineEvent';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ArrowLeft, FileText, Download } from 'lucide-react';
import Link from 'next/link';

export default function PairDetailPage() {
  const params = useParams();
  const router = useRouter();
  const pairId = params.id as string;

  const [pair, setPair] = useState<DocumentPairDetail | null>(null);
  const [comparisons, setComparisons] = useState<LineItemComparison[]>([]);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    if (pairId) {
      loadPairDetail();
    }
  }, [pairId]);

  const loadPairDetail = async () => {
    setLoading(true);
    try {
      const [pairData, comparisonData, timelineData] = await Promise.all([
        pairsApi.getById(pairId),
        pairsApi.getComparison(pairId),
        pairsApi.getTimeline(pairId),
      ]);
      setPair(pairData);
      setComparisons(comparisonData);
      setTimeline(timelineData);
    } catch (error) {
      console.error('Error loading pair detail:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleResolveIssue = async (
    issueId: string,
    action: 'accepted' | 'overridden' | 'corrected'
  ) => {
    try {
      await pairsApi.resolveIssue(pairId, issueId, action);
      await loadPairDetail(); // Reload to get updated data
    } catch (error) {
      console.error('Error resolving issue:', error);
    }
  };

  const handleApprove = async (notes?: string) => {
    try {
      await pairsApi.approve(pairId, notes);
      await loadPairDetail();
    } catch (error) {
      console.error('Error approving pair:', error);
    }
  };

  const handleReject = async (reason: string) => {
    try {
      await pairsApi.reject(pairId, reason);
      await loadPairDetail();
    } catch (error) {
      console.error('Error rejecting pair:', error);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-center py-12">Loading pair details...</div>
      </div>
    );
  }

  if (!pair) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-center py-12 text-gray-500">Pair not found</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/matching/pairs"
          className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Pairs
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold mb-2">
              Invoice #{pair.invoice_number} ↔ PO #{pair.po_number || 'N/A'}
            </h1>
            <p className="text-gray-600">
              {pair.vendor_name && `Vendor: ${pair.vendor_name}`}
              {pair.total_amount && ` • Amount: $${Number(pair.total_amount).toFixed(2)}`}
            </p>
          </div>
          <div className="flex gap-2">
            {pair.invoice.pdf_storage_path && (
              <Button variant="outline" size="sm">
                <FileText className="w-4 h-4 mr-2" />
                View Invoice
              </Button>
            )}
            {pair.purchase_order?.pdf_storage_path && (
              <Button variant="outline" size="sm">
                <FileText className="w-4 h-4 mr-2" />
                View PO
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Workflow Stepper */}
      <div className="bg-white border rounded-lg p-6 mb-6">
        <WorkflowStepper
          currentStage={pair.current_stage}
          pairStatus={pair.overall_status}
          timestamps={pair.stage_timestamps}
        />
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="mb-6">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="matching">AI Matching</TabsTrigger>
          <TabsTrigger value="line-items">Line Items</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="documents">Documents</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <MatchSummaryCard pair={pair} />
          <IssuesList issues={pair.validation_issues} onResolveIssue={handleResolveIssue} />
          <AIReasoningCard pair={pair} />
          <ApprovalActions
            pairId={pairId}
            onApprove={handleApprove}
            onReject={handleReject}
            requiresReview={pair.requires_review}
          />
        </TabsContent>

        {/* AI Matching Tab */}
        <TabsContent value="matching" className="space-y-6">
          <div className="bg-white border rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Matching Details</h3>
            {pair.matching_result && (
              <div className="space-y-4">
                <div>
                  <strong>Match Confidence:</strong>{' '}
                  {pair.confidence_score
                    ? `${(pair.confidence_score * 100).toFixed(0)}%`
                    : 'N/A'}
                </div>
                <div>
                  <strong>Matched By:</strong> {pair.matching_result.matched_by || 'N/A'}
                </div>
                <div>
                  <strong>Matched At:</strong>{' '}
                  {new Date(pair.matching_result.matched_at).toLocaleString()}
                </div>
                {pair.matching_result.issues && pair.matching_result.issues.length > 0 && (
                  <div>
                    <strong>Issues Found:</strong> {pair.matching_result.issues.length}
                  </div>
                )}
              </div>
            )}
            {pair.reasoning && (
              <div className="mt-6">
                <AIReasoningCard pair={pair} />
              </div>
            )}
          </div>
        </TabsContent>

        {/* Line Items Tab */}
        <TabsContent value="line-items" className="space-y-6">
          {comparisons.length === 0 ? (
            <div className="text-center py-12 text-gray-500">No line item comparisons available</div>
          ) : (
            comparisons.map((comparison) => (
              <LineItemRow key={comparison.line_number} comparison={comparison} />
            ))
          )}
        </TabsContent>

        {/* Timeline Tab */}
        <TabsContent value="timeline" className="space-y-6">
          <div className="bg-white border rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Activity Timeline</h3>
            {timeline.length === 0 ? (
              <div className="text-center py-12 text-gray-500">No timeline events</div>
            ) : (
              <div>
                {timeline.map((entry, idx) => (
                  <TimelineEvent key={idx} entry={entry} />
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        {/* Documents Tab */}
        <TabsContent value="documents" className="space-y-6">
          <div className="grid grid-cols-2 gap-6">
            {/* Invoice Document */}
            <div className="bg-white border rounded-lg p-6">
              <h3 className="text-lg font-semibold mb-4">Invoice Document</h3>
              <div className="space-y-2">
                <div>
                  <strong>Invoice Number:</strong> {pair.invoice.invoice_number}
                </div>
                <div>
                  <strong>Vendor:</strong> {pair.invoice.vendor_name || 'N/A'}
                </div>
                <div>
                  <strong>Amount:</strong>{' '}
                  {pair.invoice.total_amount
                    ? `$${Number(pair.invoice.total_amount).toFixed(2)}`
                    : 'N/A'}
                </div>
                {pair.invoice.pdf_storage_path && (
                  <Button variant="outline" size="sm" className="mt-4">
                    <Download className="w-4 h-4 mr-2" />
                    Download Invoice PDF
                  </Button>
                )}
              </div>
            </div>

            {/* PO Document */}
            {pair.purchase_order && (
              <div className="bg-white border rounded-lg p-6">
                <h3 className="text-lg font-semibold mb-4">Purchase Order Document</h3>
                <div className="space-y-2">
                  <div>
                    <strong>PO Number:</strong> {pair.purchase_order.po_number}
                  </div>
                  <div>
                    <strong>Vendor:</strong> {pair.purchase_order.vendor_name || 'N/A'}
                  </div>
                  <div>
                    <strong>Amount:</strong>{' '}
                    {pair.purchase_order.total_amount
                      ? `$${Number(pair.purchase_order.total_amount).toFixed(2)}`
                      : 'N/A'}
                  </div>
                  {pair.purchase_order.pdf_storage_path && (
                    <Button variant="outline" size="sm" className="mt-4">
                      <Download className="w-4 h-4 mr-2" />
                      Download PO PDF
                    </Button>
                  )}
                </div>
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

