'use client';

import { useEffect, useState } from 'react';
import { pairsApi, DocumentPairSummary } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { ArrowLeft, AlertCircle } from 'lucide-react';
import Link from 'next/link';
import { formatDistanceToNow } from 'date-fns';

export default function PairsListPage() {
  const router = useRouter();
  const [pairs, setPairs] = useState<DocumentPairSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    status: 'all' as string,
    stage: 'all' as string,
    has_issues: undefined as boolean | undefined,
  });

  useEffect(() => {
    loadPairs();
  }, [filters]);

  const loadPairs = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (filters.status !== 'all') {
        params.status = [filters.status];
      }
      if (filters.stage !== 'all') {
        params.stage = [filters.stage];
      }
      if (filters.has_issues !== undefined) {
        params.has_issues = filters.has_issues;
      }
      const data = await pairsApi.list(params);
      setPairs(data);
    } catch (error) {
      console.error('Error loading pairs:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case 'approved':
        return 'default';
      case 'needs_review':
        return 'destructive';
      case 'in_progress':
        return 'secondary';
      case 'rejected':
        return 'outline';
      default:
        return 'secondary';
    }
  };

  const getStageBadgeVariant = (stage: string) => {
    switch (stage) {
      case 'approved':
        return 'default';
      case 'validated':
        return 'secondary';
      case 'matched':
        return 'outline';
      default:
        return 'outline';
    }
  };

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Link href="/" className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-4">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Dashboard
        </Link>
        <h1 className="text-3xl font-bold mb-2">Document Pairs</h1>
        <p className="text-gray-600">Manage invoice-PO matches and their workflow stages</p>
      </div>

      {/* Filters */}
      <div className="bg-white border rounded-lg p-4 mb-6 flex gap-4 items-end">
        <div className="flex-1">
          <label className="text-sm font-medium mb-1 block">Status</label>
          <Select value={filters.status} onValueChange={(v) => setFilters({ ...filters, status: v })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="in_progress">In Progress</SelectItem>
              <SelectItem value="needs_review">Needs Review</SelectItem>
              <SelectItem value="approved">Approved</SelectItem>
              <SelectItem value="rejected">Rejected</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex-1">
          <label className="text-sm font-medium mb-1 block">Stage</label>
          <Select value={filters.stage} onValueChange={(v) => setFilters({ ...filters, stage: v })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Stages</SelectItem>
              <SelectItem value="uploaded">Uploaded</SelectItem>
              <SelectItem value="extracted">Extracted</SelectItem>
              <SelectItem value="matched">Matched</SelectItem>
              <SelectItem value="validated">Validated</SelectItem>
              <SelectItem value="approved">Approved</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex-1">
          <label className="text-sm font-medium mb-1 block">Has Issues</label>
          <Select
            value={filters.has_issues === undefined ? 'all' : filters.has_issues ? 'yes' : 'no'}
            onValueChange={(v) =>
              setFilters({ ...filters, has_issues: v === 'all' ? undefined : v === 'yes' })
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="yes">Has Issues</SelectItem>
              <SelectItem value="no">No Issues</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="text-center py-12">Loading pairs...</div>
      ) : pairs.length === 0 ? (
        <div className="text-center py-12 text-gray-500">No pairs found matching your filters.</div>
      ) : (
        <div className="bg-white border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Invoice #
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  PO #
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Vendor
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Amount
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Stage
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Issues
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Updated
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {pairs.map((pair) => (
                <tr
                  key={pair.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => router.push(`/matching/pairs/${pair.id}`)}
                >
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {pair.invoice_number}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {pair.po_number || 'N/A'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {pair.vendor_name || 'N/A'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {pair.total_amount ? `$${Number(pair.total_amount).toFixed(2)}` : 'N/A'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Badge variant={getStageBadgeVariant(pair.current_stage)}>
                      {pair.current_stage}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Badge variant={getStatusBadgeVariant(pair.overall_status)}>
                      {pair.overall_status}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {pair.issue_count > 0 ? (
                      <span className="flex items-center text-sm text-amber-600">
                        <AlertCircle className="w-4 h-4 mr-1" />
                        {pair.issue_count}
                      </span>
                    ) : (
                      <span className="text-sm text-gray-400">0</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatDistanceToNow(new Date(pair.updated_at), { addSuffix: true })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

