import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  status: string;
  className?: string;
}

const statusConfig: Record<string, { label: string; className: string }> = {
  // Old statuses (for backward compatibility)
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
  // New unified document statuses
  uploaded: {
    label: 'Uploaded',
    className: 'bg-gray-100 text-gray-800 border-gray-200',
  },
  classified: {
    label: 'Classified',
    className: 'bg-blue-100 text-blue-800 border-blue-200',
  },
  ocr_processing: {
    label: 'OCR Processing...',
    className: 'bg-blue-100 text-blue-800 border-blue-200',
  },
  pending_verification: {
    label: 'Pending Verification',
    className: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  },
  verified: {
    label: 'Verified',
    className: 'bg-green-100 text-green-800 border-green-200',
  },
};

export default function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status] || {
    label: status.charAt(0).toUpperCase() + status.slice(1).replace(/_/g, ' '),
    className: 'bg-gray-100 text-gray-800 border-gray-200',
  };
  
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

