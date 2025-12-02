'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import StatusBadge from '@/components/shared/StatusBadge';
import { Document } from '@/lib/api';
import { FileText, Play, RotateCw, Trash2, Loader2 } from 'lucide-react';

interface DocumentCardProps {
  document: Document;
  onTypeChange: (id: number, type: 'invoice' | 'purchase_order' | 'receipt') => void;
  onProcess: (id: number) => void;
  onRetry: (id: number) => void;
  onDelete: (id: number) => void;
  isProcessing?: boolean;
}

export default function DocumentCard({
  document,
  onTypeChange,
  onProcess,
  onRetry,
  onDelete,
  isProcessing = false,
}: DocumentCardProps) {
  // Can process if document is classified (has type) and not yet processed
  const canProcess = (document.status === 'classified' || document.status === 'pending') && document.document_type;
  const canRetry = document.status === 'error';
  const isReady = document.status === 'pending_verification' || document.status === 'processed';

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-6">
        <div className="flex items-start gap-4">
          <div className="rounded-lg bg-muted p-3">
            <FileText className="h-5 w-5 text-muted-foreground" />
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-4 mb-2">
              <div className="flex-1 min-w-0">
                <h3 className="font-medium text-foreground truncate mb-1">
                  {document.filename}
                </h3>
                <p className="text-xs text-muted-foreground">
                  {new Date(document.created_at).toLocaleString()}
                </p>
              </div>
              <StatusBadge status={document.status} />
            </div>

            {document.error_message && (
              <p className="text-xs text-red-600 mt-2 bg-red-50 p-2 rounded">
                {document.error_message}
              </p>
            )}

            <div className="flex items-center gap-2 mt-4 flex-wrap">
              <Select
                value={document.document_type || ''}
                onValueChange={(value) => onTypeChange(document.id, value as 'invoice' | 'purchase_order' | 'receipt')}
                disabled={document.status === 'ocr_processing' || document.status === 'processing' || isReady}
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Select type..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="invoice">Invoice</SelectItem>
                  <SelectItem value="purchase_order">Purchase Order</SelectItem>
                  <SelectItem value="receipt">Receipt</SelectItem>
                </SelectContent>
              </Select>

              {canProcess && (
                <Button
                  onClick={() => onProcess(document.id)}
                  disabled={isProcessing}
                  size="sm"
                  className="gap-2"
                >
                  {isProcessing ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4" />
                      Process
                    </>
                  )}
                </Button>
              )}

              {canRetry && (
                <Button
                  onClick={() => onRetry(document.id)}
                  disabled={isProcessing}
                  size="sm"
                  variant="outline"
                  className="gap-2"
                >
                  <RotateCw className="h-4 w-4" />
                  Retry
                </Button>
              )}

              {isReady && (
                <Button
                  onClick={() => window.location.href = `/verify/${document.id}`}
                  size="sm"
                  variant="outline"
                  className="gap-2"
                >
                  Review
                </Button>
              )}

              <Button
                onClick={() => onDelete(document.id)}
                disabled={document.status === 'processing'}
                size="sm"
                variant="ghost"
                className="gap-2 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

