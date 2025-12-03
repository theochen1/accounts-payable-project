'use client';

import { AlertCircle, CheckCircle, XCircle, Info } from 'lucide-react';
import { ValidationIssue } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

interface IssueCardProps {
  issue: ValidationIssue;
  onResolve?: (issueId: string, action: 'accepted' | 'overridden' | 'corrected') => void;
}

const severityIcons = {
  critical: XCircle,
  warning: AlertCircle,
  info: Info,
};

const severityColors = {
  critical: 'text-red-600 bg-red-50 border-red-200',
  warning: 'text-amber-600 bg-amber-50 border-amber-200',
  info: 'text-blue-600 bg-blue-50 border-blue-200',
};

export function IssueCard({ issue, onResolve }: IssueCardProps) {
  const Icon = severityIcons[issue.severity] || AlertCircle;

  return (
    <div
      className={cn(
        'border rounded-lg p-4 mb-3',
        severityColors[issue.severity],
        issue.resolved && 'opacity-60'
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3 flex-1">
          <Icon className="w-5 h-5 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-medium">{issue.category}</span>
              {issue.resolved && (
                <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">
                  Resolved
                </span>
              )}
            </div>
            <p className="text-sm mb-2">{issue.description}</p>
            {issue.field && (
              <p className="text-xs text-gray-600 mb-2">
                <strong>Field:</strong> {issue.field}
              </p>
            )}
            {issue.suggestion && (
              <div className="mt-2 p-2 bg-white rounded text-xs">
                <strong>Suggestion:</strong> {issue.suggestion}
              </div>
            )}
            {issue.resolved && issue.resolution_notes && (
              <div className="mt-2 p-2 bg-white rounded text-xs">
                <strong>Resolution:</strong> {issue.resolution_notes}
              </div>
            )}
          </div>
        </div>
      </div>

      {!issue.resolved && onResolve && (
        <div className="mt-3 flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => onResolve(issue.id, 'accepted')}
            className="text-xs"
          >
            Accept
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onResolve(issue.id, 'overridden')}
            className="text-xs"
          >
            Override
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onResolve(issue.id, 'corrected')}
            className="text-xs"
          >
            Correct
          </Button>
        </div>
      )}
    </div>
  );
}

