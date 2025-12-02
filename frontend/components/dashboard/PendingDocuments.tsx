'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import StatusBadge from '@/components/shared/StatusBadge';
import { Document } from '@/lib/api';
import { ArrowRight, FileText } from 'lucide-react';
import Link from 'next/link';

interface PendingDocumentsProps {
  documents: Document[];
  onViewAll?: () => void;
}

export default function PendingDocuments({ documents, onViewAll }: PendingDocumentsProps) {
  const recentDocs = documents.slice(0, 5);

  if (recentDocs.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Recent Documents</CardTitle>
          {onViewAll && (
            <Button variant="ghost" size="sm" onClick={onViewAll} className="gap-2">
              View All
              <ArrowRight className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {recentDocs.map((doc) => (
            <Link
              key={doc.id}
              href={`/verify/${doc.id}`}
              className="flex items-center justify-between rounded-lg border border-border p-3 transition-colors hover:bg-muted"
            >
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <div className="rounded bg-muted p-2">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">
                    {doc.filename}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(doc.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <StatusBadge status={doc.status} />
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

