'use client';

import { LineItemComparison } from '@/lib/api';
import { FieldHighlight } from './FieldHighlight';
import { cn } from '@/lib/utils';
import { CheckCircle, AlertCircle, XCircle } from 'lucide-react';

interface LineItemRowProps {
  comparison: LineItemComparison;
}

const matchStatusIcons = {
  perfect: CheckCircle,
  partial: AlertCircle,
  mismatch: XCircle,
  missing: XCircle,
};

const matchStatusColors = {
  perfect: 'text-green-600',
  partial: 'text-amber-600',
  mismatch: 'text-red-600',
  missing: 'text-gray-600',
};

export function LineItemRow({ comparison }: LineItemRowProps) {
  const StatusIcon = matchStatusIcons[comparison.overall_match] || AlertCircle;

  return (
    <div className="border rounded-lg p-4 mb-4">
      <div className="flex items-center justify-between mb-4">
        <h4 className="font-semibold text-lg">Line Item #{comparison.line_number}</h4>
        <span className={cn('flex items-center gap-1 text-sm', matchStatusColors[comparison.overall_match])}>
          <StatusIcon className="w-4 h-4" />
          {comparison.overall_match.charAt(0).toUpperCase() + comparison.overall_match.slice(1)} Match
        </span>
      </div>

      {comparison.field_comparisons.map((field, idx) => (
        <FieldHighlight
          key={idx}
          label={field.field_name}
          invoiceValue={field.invoice_value}
          poValue={field.po_value}
          isMatch={field.match}
          similarity={field.similarity}
          diffExplanation={field.diff_explanation}
        />
      ))}

      {comparison.issues.length > 0 && (
        <div className="mt-4 pt-4 border-t">
          <h5 className="text-sm font-medium mb-2">Issues:</h5>
          <ul className="list-disc list-inside text-sm text-gray-600">
            {comparison.issues.map((issue, idx) => (
              <li key={idx}>{issue.description}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

