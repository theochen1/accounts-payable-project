'use client';

import { DocumentPairDetail } from '@/lib/api';
import { CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MatchSummaryCardProps {
  pair: DocumentPairDetail;
}

export function MatchSummaryCard({ pair }: MatchSummaryCardProps) {
  const invoice = pair.invoice;
  const po = pair.purchase_order;

  const comparisons = [
    {
      label: 'Invoice Number',
      invoiceValue: invoice.invoice_number,
      poValue: po?.po_number || 'N/A',
      match: true,
    },
    {
      label: 'Vendor',
      invoiceValue: invoice.vendor_name || 'N/A',
      poValue: po?.vendor_name || 'N/A',
      match: invoice.vendor_name === po?.vendor_name,
    },
    {
      label: 'Total Amount',
      invoiceValue: invoice.total_amount ? `$${Number(invoice.total_amount).toFixed(2)}` : 'N/A',
      poValue: po?.total_amount ? `$${Number(po.total_amount).toFixed(2)}` : 'N/A',
      match: invoice.total_amount && po?.total_amount
        ? Math.abs(Number(invoice.total_amount) - Number(po.total_amount)) < 0.01
        : false,
    },
    {
      label: 'Currency',
      invoiceValue: invoice.currency,
      poValue: po?.currency || 'N/A',
      match: invoice.currency === po?.currency,
    },
  ];

  return (
    <div className="border rounded-lg p-6 mb-6">
      <h3 className="text-lg font-semibold mb-4">Match Summary</h3>
      <div className="space-y-3">
        {comparisons.map((comp, idx) => (
          <div key={idx} className="flex items-center justify-between py-2 border-b last:border-0">
            <div className="flex-1">
              <div className="text-sm font-medium text-gray-700">{comp.label}</div>
              <div className="grid grid-cols-2 gap-4 mt-1">
                <div>
                  <div className="text-xs text-gray-500">Invoice</div>
                  <div className="text-sm">{String(comp.invoiceValue)}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">PO</div>
                  <div className="text-sm">{String(comp.poValue)}</div>
                </div>
              </div>
            </div>
            <div className="ml-4">
              {comp.match ? (
                <CheckCircle className="w-5 h-5 text-green-600" />
              ) : (
                <XCircle className="w-5 h-5 text-red-600" />
              )}
            </div>
          </div>
        ))}
      </div>
      {pair.confidence_score !== undefined && (
        <div className="mt-4 pt-4 border-t">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Confidence Score</span>
            <span className={cn(
              'text-sm font-semibold',
              pair.confidence_score >= 0.8 ? 'text-green-600' : 
              pair.confidence_score >= 0.6 ? 'text-amber-600' : 'text-red-600'
            )}>
              {(pair.confidence_score * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

