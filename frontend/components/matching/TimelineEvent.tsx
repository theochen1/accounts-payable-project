'use client';

import { TimelineEntry } from '@/lib/api';
import { format } from 'date-fns';
import { Circle } from 'lucide-react';

interface TimelineEventProps {
  entry: TimelineEntry;
}

const eventIcons: Record<string, string> = {
  uploaded: '📄',
  extracted: '🔍',
  matched: '🔗',
  validated: '✓',
  approved: '👤',
  issue_resolved: '✅',
};

export function TimelineEvent({ entry }: TimelineEventProps) {
  return (
    <div className="flex gap-4 pb-6 last:pb-0">
      <div className="flex flex-col items-center">
        <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-sm">
          {eventIcons[entry.event_type] || '•'}
        </div>
        <div className="w-0.5 h-full bg-gray-200 mt-2" />
      </div>
      <div className="flex-1 pb-4">
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm font-medium text-gray-900">{entry.description}</span>
          <span className="text-xs text-gray-500">
            {format(new Date(entry.timestamp), 'MMM d, yyyy h:mm a')}
          </span>
        </div>
        {entry.actor && (
          <div className="text-xs text-gray-500">by {entry.actor}</div>
        )}
        {entry.details && Object.keys(entry.details).length > 0 && (
          <div className="mt-2 text-xs text-gray-600 bg-gray-50 p-2 rounded">
            {JSON.stringify(entry.details, null, 2)}
          </div>
        )}
      </div>
    </div>
  );
}

