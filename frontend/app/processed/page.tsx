'use client';

import { useState, useEffect } from 'react';
import { documentApi, ProcessedDocument } from '@/lib/api';
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
import { useToast } from '@/components/ui/use-toast';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import EmptyState from '@/components/shared/EmptyState';
import { FileText, ArrowRight, Trash2 } from 'lucide-react';
import Link from 'next/link';

export default function ProcessedPage() {
  const [documents, setDocuments] = useState<ProcessedDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<ProcessedDocument | null>(null);
  const [deleting, setDeleting] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadDocuments();
  }, [filter]);

  const loadDocuments = async () => {
    try {
      const docs = await documentApi.listProcessed(filter === 'all' ? undefined : filter);
      setDocuments(docs);
    } catch (error) {
      console.error('Failed to load processed documents:', error);
      toast({
        title: 'Error',
        description: 'Failed to load processed documents',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteClick = (doc: ProcessedDocument) => {
    setDocumentToDelete(doc);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!documentToDelete) return;

    setDeleting(true);
    try {
      await documentApi.delete(documentToDelete.id);
      toast({
        title: 'Success',
        description: 'Document deleted successfully',
      });
      setDeleteDialogOpen(false);
      setDocumentToDelete(null);
      // Reload documents
      await loadDocuments();
    } catch (error) {
      console.error('Failed to delete document:', error);
      toast({
        title: 'Error',
        description: 'Failed to delete document',
        variant: 'destructive',
      });
    } finally {
      setDeleting(false);
    }
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
        title="Processed Documents"
        description="View all processed invoices and purchase orders"
      />
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-7xl mx-auto space-y-6">
          <div className="flex items-center justify-between">
            <Select value={filter} onValueChange={setFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Documents</SelectItem>
                <SelectItem value="invoice">Invoices</SelectItem>
                <SelectItem value="purchase_order">Purchase Orders</SelectItem>
                <SelectItem value="receipt">Receipts</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {documents.length === 0 ? (
            <EmptyState
              title="No processed documents"
              description="Documents that have been processed and saved will appear here."
            />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Processed Documents ({documents.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead>Reference Number</TableHead>
                      <TableHead>Vendor</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {documents.map((doc) => (
                      <TableRow key={doc.id} className="hover:bg-muted/50">
                        <TableCell>
                          <span className="inline-flex items-center rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
                            {(doc.document_type === 'po' ? 'PURCHASE ORDER' : doc.document_type === 'purchase_order' ? 'PURCHASE ORDER' : doc.document_type.toUpperCase())}
                          </span>
                        </TableCell>
                        <TableCell className="font-medium">{doc.document_number || doc.reference_number || '-'}</TableCell>
                        <TableCell>{doc.vendor_name || '-'}</TableCell>
                        <TableCell>
                          {(doc.document_date || doc.date) ? new Date(doc.document_date || doc.date!).toLocaleDateString() : '-'}
                        </TableCell>
                        <TableCell className="text-right font-medium">
                          {doc.total_amount
                            ? `${doc.currency} ${doc.total_amount.toLocaleString('en-US', {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })}`
                            : '-'}
                        </TableCell>
                        <TableCell>
                          <span
                            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                              doc.status === 'approved'
                                ? 'bg-green-100 text-green-800'
                                : doc.status === 'rejected'
                                ? 'bg-red-100 text-red-800'
                                : 'bg-yellow-100 text-yellow-800'
                            }`}
                          >
                            {doc.status}
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <Link
                              href={
                                doc.document_type === 'invoice'
                                  ? `/invoices/${doc.id}`
                                  : `/purchase-orders/${doc.document_number || doc.reference_number || doc.id}`
                              }
                              className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                            >
                              View
                              <ArrowRight className="h-3 w-3" />
                            </Link>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteClick(doc)}
                              className="text-destructive hover:text-destructive hover:bg-destructive/10"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Document</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this document? This action cannot be undone.
              {documentToDelete && (
                <div className="mt-2 p-2 bg-muted rounded text-sm">
                  <div><strong>Type:</strong> {documentToDelete.document_type.toUpperCase()}</div>
                  <div><strong>Reference:</strong> {documentToDelete.document_number || documentToDelete.reference_number || '-'}</div>
                  {documentToDelete.vendor_name && (
                    <div><strong>Vendor:</strong> {documentToDelete.vendor_name}</div>
                  )}
                </div>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setDeleteDialogOpen(false);
                setDocumentToDelete(null);
              }}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={deleting}
            >
              {deleting ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

