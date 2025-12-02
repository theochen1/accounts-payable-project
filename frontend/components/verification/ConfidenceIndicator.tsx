import { cn } from '@/lib/utils';
import { AlertCircle } from 'lucide-react';

interface ConfidenceIndicatorProps {
  confidence?: number;
  className?: string;
}

export default function ConfidenceIndicator({ confidence, className }: ConfidenceIndicatorProps) {
  if (confidence === undefined || confidence === null) {
    return null;
  }

  const isLow = confidence < 0.7;
  const isMedium = confidence >= 0.7 && confidence < 0.9;
  const isHigh = confidence >= 0.9;

  return (
    <div className={cn('flex items-center gap-2', className)}>
      {isLow && (
        <div className="flex items-center gap-1 text-amber-600">
          <AlertCircle className="h-3 w-3" />
          <span className="text-xs">Low confidence</span>
        </div>
      )}
      {isMedium && (
        <span className="text-xs text-muted-foreground">
          {Math.round(confidence * 100)}% confidence
        </span>
      )}
      {isHigh && (
        <span className="text-xs text-muted-foreground">
          {Math.round(confidence * 100)}% confidence
        </span>
      )}
    </div>
  );
}

