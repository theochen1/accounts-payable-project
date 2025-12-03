'use client';

import { DocumentPairDetail } from '@/lib/api';
import { Sparkles } from 'lucide-react';

interface AIReasoningCardProps {
  pair: DocumentPairDetail;
}

export function AIReasoningCard({ pair }: AIReasoningCardProps) {
  if (!pair.reasoning) {
    return null;
  }

  return (
    <div className="border rounded-lg p-6 mb-6 bg-blue-50/50">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="w-5 h-5 text-blue-600" />
        <h3 className="text-lg font-semibold">AI Reasoning</h3>
      </div>
      <p className="text-sm text-gray-700 whitespace-pre-wrap">{pair.reasoning}</p>
      {pair.matching_result?.matched_by && (
        <div className="mt-3 text-xs text-gray-500">
          Matched by: {pair.matching_result.matched_by} •{' '}
          {new Date(pair.matching_result.matched_at).toLocaleString()}
        </div>
      )}
    </div>
  );
}

