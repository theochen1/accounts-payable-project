'use client';

import { ValidationIssue } from '@/lib/api';
import { IssueCard } from './IssueCard';
import { useState } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface IssuesListProps {
  issues: ValidationIssue[];
  onResolveIssue?: (issueId: string, action: 'accepted' | 'overridden' | 'corrected') => void;
}

export function IssuesList({ issues, onResolveIssue }: IssuesListProps) {
  const [filter, setFilter] = useState<'all' | 'unresolved' | 'resolved'>('all');

  const filteredIssues = issues.filter((issue) => {
    if (filter === 'unresolved') return !issue.resolved;
    if (filter === 'resolved') return issue.resolved;
    return true;
  });

  const unresolvedCount = issues.filter((i) => !i.resolved).length;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">
          Issues Detected ({unresolvedCount} unresolved)
        </h3>
        <Select value={filter} onValueChange={(v: any) => setFilter(v)}>
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Issues</SelectItem>
            <SelectItem value="unresolved">Unresolved</SelectItem>
            <SelectItem value="resolved">Resolved</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {filteredIssues.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          {filter === 'unresolved' ? 'No unresolved issues' : 'No issues found'}
        </div>
      ) : (
        <div className="space-y-2">
          {filteredIssues.map((issue) => (
            <IssueCard key={issue.id} issue={issue} onResolve={onResolveIssue} />
          ))}
        </div>
      )}
    </div>
  );
}

