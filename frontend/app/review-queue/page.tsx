'use client';

import { useState, useEffect } from 'react';
import { matchingApi, ReviewQueueItem, MatchingIssueV2 } from '@/lib/api';
import Header from '@/components/layout/Header';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/use-toast';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import EmptyState from '@/components/shared/EmptyState';
import { AlertCircle, CheckCircle2, XCircle, Clock, AlertTriangle } from 'lucide-react';

export default function ReviewQueuePage() {
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('pending');
  const [selectedItem, setSelectedItem] = useState<ReviewQueueItem | null>(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [resolveModalOpen, setResolveModalOpen] = useState(false);
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [resolving, setResolving] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadQueue();
  }, [priorityFilter, categoryFilter, statusFilter]);

  const loadQueue = async () => {
    try {
      setLoading(true);
      const params: any = {
        status: statusFilter === 'all' ? undefined : statusFilter,
        limit: 100,
      };
      if (priorityFilter !== 'all') {
        params.priority = priorityFilter;
      }
      if (categoryFilter !== 'all') {
        params.issue_category = categoryFilter;
      }
      const queueItems = await matchingApi.listReviewQueue(params);
      setItems(queueItems);
    } catch (error) {
      console.error('Failed to load review queue:', error);
      toast({
        title: 'Error',
        description: 'Failed to load review queue',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleRowClick = (item: ReviewQueueItem) => {
    setSelectedItem(item);
    setDetailModalOpen(true);
  };

  const handleResolveClick = (item: ReviewQueueItem) => {
    setSelectedItem(item);
    setResolutionNotes('');
    setResolveModalOpen(true);
  };

  const handleResolve = async (resolution: 'approved' | 'rejected') => {
    if (!selectedItem) return;

    setResolving(true);
    try {
      await matchingApi.resolveQueueItem(selectedItem.id, resolution, resolutionNotes);
      toast({
        title: 'Success',
        description: `Item ${resolution === 'approved' ? 'approved' : 'rejected'} successfully`,
      });
      setResolveModalOpen(false);
      setSelectedItem(null);
      setResolutionNotes('');
      await loadQueue();
    } catch (error: any) {
      console.error('Failed to resolve item:', error);
      toast({
        title: 'Error',
        description: error.response?.data?.detail || 'Failed to resolve item',
        variant: 'destructive',
      });
    } finally {
      setResolving(false);
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'high':
        return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'low':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getPriorityIcon = (priority: string) => {
    switch (priority) {
      case 'critical':
        return <AlertCircle className="h-4 w-4" />;
      case 'high':
        return <AlertTriangle className="h-4 w-4" />;
      default:
        return <Clock className="h-4 w-4" />;
    }
  };

  const getSlaStatus = (deadline?: string) => {
    if (!deadline) return null;
    const deadlineDate = new Date(deadline);
    const now = new Date();
    const hoursUntilDeadline = (deadlineDate.getTime() - now.getTime()) / (1000 * 60 * 60);
    
    if (hoursUntilDeadline < 0) {
      return { status: 'overdue', text: 'Overdue', color: 'text-red-600' };
    } else if (hoursUntilDeadline < 2) {
      return { status: 'urgent', text: 'Due soon', color: 'text-orange-600' };
    } else {
      const hours = Math.floor(hoursUntilDeadline);
      const minutes = Math.floor((hoursUntilDeadline - hours) * 60);
      let text = '';
      if (hours > 0) {
        text = `${hours}h ${minutes}m`;
      } else {
        text = `${minutes}m`;
      }
      return { status: 'ok', text: `Due in ${text}`, color: 'text-gray-600' };
    }
  };

  // Get unique issue categories for filter
  const issueCategories = Array.from(new Set(items.map(item => item.issue_category)));

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
        title="Review Queue"
        description="Items requiring human review and approval"
      />
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-7xl mx-auto space-y-6">
          <div className="flex items-center gap-4">
            <Select value={priorityFilter} onValueChange={setPriorityFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Priority" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Priorities</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>

            <Select value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder="Issue Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                {issueCategories.map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {cat.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
                <SelectItem value="all">All</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {items.length === 0 ? (
            <EmptyState
              title="No items in review queue"
              description="Items requiring review will appear here after matching."
            />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Review Queue ({items.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Invoice #</TableHead>
                      <TableHead>Vendor</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Issue Category</TableHead>
                      <TableHead>Priority</TableHead>
                      <TableHead>SLA</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {items.map((item) => {
                      const matchingResult = item.matching_result;
                      const invoiceId = matchingResult?.invoice_id;
                      const slaStatus = getSlaStatus(item.sla_deadline);
                      
                      return (
                        <TableRow
                          key={item.id}
                          className="hover:bg-muted/50 cursor-pointer"
                          onClick={() => handleRowClick(item)}
                        >
                          <TableCell className="font-medium">
                            {matchingResult?.invoice_number || (invoiceId ? `#${invoiceId}` : '-')}
                          </TableCell>
                          <TableCell>{matchingResult?.vendor_name || '-'}</TableCell>
                          <TableCell>
                            {matchingResult?.total_amount && matchingResult?.currency
                              ? `${matchingResult.currency} ${matchingResult.total_amount.toLocaleString('en-US', {
                                  minimumFractionDigits: 2,
                                  maximumFractionDigits: 2,
                                })}`
                              : '-'}
                          </TableCell>
                          <TableCell>
                            <span className="text-sm">
                              {item.issue_category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                            </span>
                          </TableCell>
                          <TableCell>
                            <span
                              className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${getPriorityColor(item.priority)}`}
                            >
                              {getPriorityIcon(item.priority)}
                              {item.priority.toUpperCase()}
                            </span>
                          </TableCell>
                          <TableCell>
                            {slaStatus && (
                              <span className={`text-xs ${slaStatus.color}`}>
                                {slaStatus.text}
                              </span>
                            )}
                          </TableCell>
                          <TableCell>
                            {item.resolved_at ? (
                              <span className="inline-flex items-center gap-1 rounded-full bg-green-100 text-green-800 px-2.5 py-0.5 text-xs font-medium">
                                <CheckCircle2 className="h-3 w-3" />
                                Resolved
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 rounded-full bg-yellow-100 text-yellow-800 px-2.5 py-0.5 text-xs font-medium">
                                <Clock className="h-3 w-3" />
                                Pending
                              </span>
                            )}
                          </TableCell>
                          <TableCell onClick={(e) => e.stopPropagation()}>
                            {!item.resolved_at && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleResolveClick(item)}
                              >
                                Resolve
                              </Button>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Detail Modal */}
      <Dialog open={detailModalOpen} onOpenChange={setDetailModalOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Review Queue Item Details</DialogTitle>
            <DialogDescription>
              Invoice-PO matching details and issues
            </DialogDescription>
          </DialogHeader>
          {selectedItem && selectedItem.matching_result && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h4 className="font-semibold mb-2">Invoice</h4>
                  <p className="text-sm text-muted-foreground">
                    Invoice ID: {selectedItem.matching_result.invoice_id}
                  </p>
                  {selectedItem.matching_result.po_id && (
                    <p className="text-sm text-muted-foreground">
                      PO ID: {selectedItem.matching_result.po_id}
                    </p>
                  )}
                </div>
                <div>
                  <h4 className="font-semibold mb-2">Match Status</h4>
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      selectedItem.matching_result.match_status === 'matched'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-yellow-100 text-yellow-800'
                    }`}
                  >
                    {selectedItem.matching_result.match_status}
                  </span>
                  {selectedItem.matching_result.confidence_score !== undefined && (
                    <p className="text-sm text-muted-foreground mt-1">
                      Confidence: {(selectedItem.matching_result.confidence_score * 100).toFixed(0)}%
                    </p>
                  )}
                </div>
              </div>

              {selectedItem.matching_result.reasoning && (
                <div>
                  <h4 className="font-semibold mb-2">Agent Reasoning</h4>
                  <p className="text-sm text-muted-foreground bg-muted p-3 rounded">
                    {selectedItem.matching_result.reasoning}
                  </p>
                </div>
              )}

              {selectedItem.matching_result.issues && selectedItem.matching_result.issues.length > 0 && (
                <div>
                  <h4 className="font-semibold mb-2">Issues Found</h4>
                  <div className="space-y-2">
                    {selectedItem.matching_result.issues.map((issue: MatchingIssueV2, idx: number) => (
                      <div
                        key={idx}
                        className={`border rounded p-3 ${
                          issue.severity === 'critical'
                            ? 'border-red-200 bg-red-50'
                            : issue.severity === 'high'
                            ? 'border-orange-200 bg-orange-50'
                            : issue.severity === 'medium'
                            ? 'border-yellow-200 bg-yellow-50'
                            : 'border-blue-200 bg-blue-50'
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <p className="font-medium text-sm">{issue.message}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                              Category: {issue.category.replace(/_/g, ' ')}
                            </p>
                            {issue.line_number && (
                              <p className="text-xs text-muted-foreground">
                                Line: {issue.line_number}
                              </p>
                            )}
                          </div>
                          <span
                            className={`text-xs font-medium px-2 py-1 rounded ${
                              issue.severity === 'critical'
                                ? 'bg-red-100 text-red-800'
                                : issue.severity === 'high'
                                ? 'bg-orange-100 text-orange-800'
                                : issue.severity === 'medium'
                                ? 'bg-yellow-100 text-yellow-800'
                                : 'bg-blue-100 text-blue-800'
                            }`}
                          >
                            {issue.severity.toUpperCase()}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDetailModalOpen(false)}>
              Close
            </Button>
            {selectedItem && !selectedItem.resolved_at && (
              <Button onClick={() => {
                setDetailModalOpen(false);
                handleResolveClick(selectedItem);
              }}>
                Resolve
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Resolve Modal */}
      <Dialog open={resolveModalOpen} onOpenChange={setResolveModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Resolve Review Queue Item</DialogTitle>
            <DialogDescription>
              Approve or reject this matching result
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Resolution Notes (Optional)</label>
              <Textarea
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
                placeholder="Add any notes about this resolution..."
                className="mt-1"
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setResolveModalOpen(false);
                setResolutionNotes('');
              }}
              disabled={resolving}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => handleResolve('rejected')}
              disabled={resolving}
            >
              {resolving ? 'Rejecting...' : 'Reject'}
            </Button>
            <Button
              onClick={() => handleResolve('approved')}
              disabled={resolving}
            >
              {resolving ? 'Approving...' : 'Approve'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

