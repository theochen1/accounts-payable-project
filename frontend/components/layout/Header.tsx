'use client';

import { Button } from '@/components/ui/button';
import { Upload } from 'lucide-react';

interface HeaderProps {
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export default function Header({ title, description, action }: HeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-border bg-background px-8 py-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          {title}
        </h1>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {action && (
        <Button onClick={action.onClick} className="gap-2">
          <Upload className="h-4 w-4" />
          {action.label}
        </Button>
      )}
    </div>
  );
}

