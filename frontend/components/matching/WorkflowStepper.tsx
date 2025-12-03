'use client';

import { CheckCircle, Circle, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { WorkflowStage, PairStatus, StageTimestamps } from '@/lib/api';
import { formatDistanceToNow } from 'date-fns';

interface WorkflowStepperProps {
  currentStage: WorkflowStage;
  pairStatus: PairStatus;
  timestamps: StageTimestamps;
}

const stages = [
  { id: 1, name: 'Uploaded', key: 'uploaded' as WorkflowStage },
  { id: 2, name: 'Extracted', key: 'extracted' as WorkflowStage },
  { id: 3, name: 'Matched', key: 'matched' as WorkflowStage },
  { id: 4, name: 'Validated', key: 'validated' as WorkflowStage },
  { id: 5, name: 'Approved', key: 'approved' as WorkflowStage },
];

const stageIcons: Record<WorkflowStage, string> = {
  uploaded: '📄',
  extracted: '🔍',
  matched: '🔗',
  validated: '✓',
  approved: '👤',
};

export function WorkflowStepper({ currentStage, pairStatus, timestamps }: WorkflowStepperProps) {
  const currentStageIndex = stages.findIndex((s) => s.key === currentStage);
  const hasIssue = pairStatus === 'needs_review';

  return (
    <div className="w-full py-6">
      <div className="flex items-center justify-between">
        {stages.map((stage, index) => {
          const isComplete = index < currentStageIndex;
          const isCurrent = index === currentStageIndex;
          const stageTimestamp = timestamps[stage.key as keyof StageTimestamps];

          return (
            <div key={stage.id} className="flex items-center flex-1">
              {/* Stage indicator */}
              <div className="flex flex-col items-center flex-1">
                <div
                  className={cn(
                    'rounded-full w-12 h-12 flex items-center justify-center text-lg border-2 transition-all',
                    isComplete && 'bg-green-500 border-green-500 text-white',
                    isCurrent && !hasIssue && 'bg-blue-500 border-blue-500 text-white animate-pulse',
                    isCurrent && hasIssue && 'bg-amber-500 border-amber-500 text-white',
                    !isComplete && !isCurrent && 'bg-gray-100 border-gray-300 text-gray-400'
                  )}
                >
                  {isComplete ? (
                    <CheckCircle className="w-6 h-6" />
                  ) : hasIssue && isCurrent ? (
                    <AlertCircle className="w-6 h-6" />
                  ) : (
                    <span>{stageIcons[stage.key]}</span>
                  )}
                </div>
                <div className="mt-2 text-sm font-medium text-gray-700">{stage.name}</div>
                {stageTimestamp && (
                  <div className="text-xs text-gray-500 mt-1">
                    {formatDistanceToNow(new Date(stageTimestamp), { addSuffix: true })}
                  </div>
                )}
              </div>

              {/* Connector line */}
              {index < stages.length - 1 && (
                <div
                  className={cn(
                    'flex-1 h-1 mx-2 transition-colors',
                    isComplete ? 'bg-green-500' : 'bg-gray-200'
                  )}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Current status */}
      <div className="mt-6 text-center">
        <p className="text-sm text-gray-600">
          Current Stage:{' '}
          <span className="font-semibold">{stages[currentStageIndex]?.name || 'Unknown'}</span>
        </p>
        {hasIssue && (
          <p className="text-sm text-amber-600 mt-1">⚠ Requires attention before proceeding</p>
        )}
      </div>
    </div>
  );
}

