'use client';

import { useState, useEffect } from 'react';
import { documentApi, ProcessedDocument } from '@/lib/api';
import Header from '@/components/layout/Header';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import EmptyState from '@/components/shared/EmptyState';
import { FileText, ArrowRight } from 'lucide-react';
import Link from 'next/link';

export default function ProcessedPage() {
  const [documents, setDocuments] = useState<ProcessedDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    loadDocuments();
  }, [filter]);

  const loadDocuments = async () => {
    try {
      const docs = await documentApi.listProcessed(filter === 'all' ? undefined : filter);
      setDocuments(docs);
    } catch (error) {
      console.error('Failed to load processed documents:', error);
    } finally {
      setLoading(false);
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
                <SelectItem value="po">Purchase Orders</SelectItem>
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
                            {doc.document_type.toUpperCase()}
                          </span>
                        </TableCell>
                        <TableCell className="font-medium">{doc.reference_number}</TableCell>
                        <TableCell>{doc.vendor_name || '-'}</TableCell>
                        <TableCell>
                          {doc.date ? new Date(doc.date).toLocaleDateString() : '-'}
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
                          <Link
                            href={
                              doc.document_type === 'invoice'
                                ? `/invoices/${doc.id}`
                                : `/purchase-orders/${doc.reference_number}`
                            }
                            className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                          >
                            View
                            <ArrowRight className="h-3 w-3" />
                          </Link>
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
    </div>
  );
}

