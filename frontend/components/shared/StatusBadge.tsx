import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  status: 'pending' | 'processing' | 'processed' | 'error';
  className?: string;
}

const statusConfig = {
  pending: {
    label: 'Pending',
    className: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  },
  processing: {
    label: 'Processing...',
    className: 'bg-blue-100 text-blue-800 border-blue-200',
  },
  processed: {
    label: 'Processed',
    className: 'bg-green-100 text-green-800 border-green-200',
  },
  error: {
    label: 'Error',
    className: 'bg-red-100 text-red-800 border-red-200',
  },
};

export default function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status];
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium',
        config.className,
        className
      )}
    >
      {config.label}
    </span>
  );
}

