'use client';

import { CheckCircle, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FieldHighlightProps {
  label: string;
  invoiceValue: string | number;
  poValue: string | number;
  isMatch: boolean;
  similarity?: number;
  diffExplanation?: string;
}

export function FieldHighlight({
  label,
  invoiceValue,
  poValue,
  isMatch,
  similarity,
  diffExplanation,
}: FieldHighlightProps) {
  return (
    <div className="border rounded-lg p-4 mb-4">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-medium text-gray-900">{label}</h4>
        {isMatch ? (
          <span className="flex items-center text-green-600 text-sm">
            <CheckCircle className="w-4 h-4 mr-1" />
            Match
          </span>
        ) : (
          <span className="flex items-center text-amber-600 text-sm">
            <AlertCircle className="w-4 h-4 mr-1" />
            Difference
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs text-gray-500 mb-1">Invoice</div>
          <div
            className={cn(
              'p-2 rounded font-mono text-sm',
              !isMatch && 'bg-red-50 border border-red-200'
            )}
          >
            {String(invoiceValue)}
          </div>
        </div>

        <div>
          <div className="text-xs text-gray-500 mb-1">Purchase Order</div>
          <div
            className={cn(
              'p-2 rounded font-mono text-sm',
              !isMatch && 'bg-green-50 border border-green-200'
            )}
          >
            {String(poValue)}
          </div>
        </div>
      </div>

      {!isMatch && diffExplanation && (
        <div className="mt-3 p-3 bg-amber-50 rounded text-sm text-amber-800">
          <strong>Difference:</strong> {diffExplanation}
          {similarity !== undefined && (
            <span className="ml-2 text-amber-600">
              (Similarity: {(similarity * 100).toFixed(0)}%)
            </span>
          )}
        </div>
      )}
    </div>
  );
}

