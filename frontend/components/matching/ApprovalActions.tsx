'use client';

import { Button } from '@/components/ui/button';
import { CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { useState } from 'react';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface ApprovalActionsProps {
  pairId: string;
  onApprove: (pairId: string, notes?: string) => Promise<void>;
  onReject: (pairId: string, reason: string) => Promise<void>;
  requiresReview?: boolean;
}

export function ApprovalActions({
  pairId,
  onApprove,
  onReject,
  requiresReview,
}: ApprovalActionsProps) {
  const [approveDialogOpen, setApproveDialogOpen] = useState(false);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);

  const handleApprove = async () => {
    setLoading(true);
    try {
      await onApprove(pairId, notes);
      setApproveDialogOpen(false);
      setNotes('');
    } catch (error) {
      console.error('Error approving pair:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    if (!notes.trim()) {
      alert('Please provide a reason for rejection');
      return;
    }
    setLoading(true);
    try {
      await onReject(pairId, notes);
      setRejectDialogOpen(false);
      setNotes('');
    } catch (error) {
      console.error('Error rejecting pair:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex gap-3 mt-6 pt-6 border-t">
      <Button
        onClick={() => setApproveDialogOpen(true)}
        disabled={loading || requiresReview}
        className="flex-1"
      >
        <CheckCircle className="w-4 h-4 mr-2" />
        Approve
      </Button>
      <Button
        onClick={() => setRejectDialogOpen(true)}
        variant="destructive"
        disabled={loading}
        className="flex-1"
      >
        <XCircle className="w-4 h-4 mr-2" />
        Reject
      </Button>

      {/* Approve Dialog */}
      <Dialog open={approveDialogOpen} onOpenChange={setApproveDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Approve Document Pair</DialogTitle>
            <DialogDescription>
              Are you sure you want to approve this invoice-PO pair?
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="approve-notes">Notes (optional)</Label>
              <Textarea
                id="approve-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add any notes about this approval..."
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setApproveDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleApprove} disabled={loading}>
              {loading ? 'Approving...' : 'Approve'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject Dialog */}
      <Dialog open={rejectDialogOpen} onOpenChange={setRejectDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Document Pair</DialogTitle>
            <DialogDescription>
              Please provide a reason for rejecting this invoice-PO pair.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="reject-reason">Reason *</Label>
              <Textarea
                id="reject-reason"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Explain why this pair is being rejected..."
                rows={3}
                required
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleReject} disabled={loading || !notes.trim()}>
              {loading ? 'Rejecting...' : 'Reject'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

