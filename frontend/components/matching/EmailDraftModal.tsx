'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { emailApi, EmailDraftResponse } from '@/lib/api';
import { Loader2, Mail, Send, X } from 'lucide-react';

interface EmailDraftModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pairId: string;
  issueIds?: string[];
  onEmailSent?: () => void;
}

export function EmailDraftModal({
  open,
  onOpenChange,
  pairId,
  issueIds,
  onEmailSent,
}: EmailDraftModalProps) {
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [draft, setDraft] = useState<EmailDraftResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editedSubject, setEditedSubject] = useState('');
  const [editedBody, setEditedBody] = useState('');

  const handleDraft = async () => {
    setLoading(true);
    setError(null);
    try {
      const draftResponse = await emailApi.draft({
        document_pair_id: pairId,
        issue_ids: issueIds,
      });
      setDraft(draftResponse);
      setEditedSubject(draftResponse.subject);
      setEditedBody(draftResponse.body_text);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to draft email');
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    if (!draft) return;

    setSending(true);
    setError(null);
    try {
      await emailApi.send({
        email_log_id: draft.email_log_id,
        subject: editedSubject !== draft.subject ? editedSubject : undefined,
        body_text: editedBody !== draft.body_text ? editedBody : undefined,
      });
      onEmailSent?.();
      onOpenChange(false);
      // Reset state
      setDraft(null);
      setEditedSubject('');
      setEditedBody('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to send email');
    } finally {
      setSending(false);
    }
  };

  const handleClose = () => {
    if (!sending) {
      onOpenChange(false);
      setDraft(null);
      setEditedSubject('');
      setEditedBody('');
      setError(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Mail className="w-5 h-5" />
            Draft Escalation Email
          </DialogTitle>
          <DialogDescription>
            Generate and send a professional email to resolve invoice-PO discrepancies
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-3">
              {error}
            </div>
          )}

          {!draft ? (
            <div className="py-8 text-center">
              <p className="text-gray-600 mb-4">
                Click the button below to generate an email draft based on the issues found.
              </p>
              <Button onClick={handleDraft} disabled={loading}>
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Generating Draft...
                  </>
                ) : (
                  <>
                    <Mail className="w-4 h-4 mr-2" />
                    Generate Email Draft
                  </>
                )}
              </Button>
            </div>
          ) : (
            <>
              {/* Recipients */}
              <div className="space-y-2">
                <Label>To</Label>
                <div className="text-sm text-gray-700 bg-gray-50 p-2 rounded">
                  {draft.to_addresses.join(', ')}
                </div>
              </div>

              {draft.cc_addresses && draft.cc_addresses.length > 0 && (
                <div className="space-y-2">
                  <Label>CC</Label>
                  <div className="text-sm text-gray-700 bg-gray-50 p-2 rounded">
                    {draft.cc_addresses.join(', ')}
                  </div>
                </div>
              )}

              {/* Subject */}
              <div className="space-y-2">
                <Label htmlFor="subject">Subject</Label>
                <Textarea
                  id="subject"
                  value={editedSubject}
                  onChange={(e) => setEditedSubject(e.target.value)}
                  className="min-h-[60px]"
                  placeholder="Email subject"
                />
              </div>

              {/* Body */}
              <div className="space-y-2">
                <Label htmlFor="body">Email Body</Label>
                <Textarea
                  id="body"
                  value={editedBody}
                  onChange={(e) => setEditedBody(e.target.value)}
                  className="min-h-[300px] font-mono text-sm"
                  placeholder="Email body"
                />
              </div>

              {/* Summary */}
              {draft.summary && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                  <p className="text-sm text-blue-900">
                    <strong>Summary:</strong> {draft.summary}
                  </p>
                </div>
              )}
            </>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={sending}>
            <X className="w-4 h-4 mr-2" />
            {draft ? 'Cancel' : 'Close'}
          </Button>
          {draft && (
            <Button onClick={handleSend} disabled={sending || !editedSubject || !editedBody}>
              {sending ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Sending...
                </>
              ) : (
                <>
                  <Send className="w-4 h-4 mr-2" />
                  Send Email
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

