'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ZoomIn, ZoomOut, RotateCw } from 'lucide-react';

interface DocumentViewerProps {
  documentUrl: string;
  filename: string;
}

export default function DocumentViewer({ documentUrl, filename }: DocumentViewerProps) {
  const [zoom, setZoom] = useState(1);

  const isPdf = filename.toLowerCase().endsWith('.pdf');

  return (
    <div className="flex flex-col h-full bg-muted/30">
      <div className="flex items-center justify-between border-b border-border bg-background px-4 py-2">
        <span className="text-sm font-medium text-foreground truncate">{filename}</span>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setZoom(Math.max(0.5, zoom - 0.25))}
            disabled={zoom <= 0.5}
          >
            <ZoomOut className="h-4 w-4" />
          </Button>
          <span className="text-xs text-muted-foreground w-12 text-center">{Math.round(zoom * 100)}%</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setZoom(Math.min(2, zoom + 0.25))}
            disabled={zoom >= 2}
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-4 flex items-center justify-center">
        {isPdf ? (
          <iframe
            src={documentUrl}
            className="w-full h-full border-0 rounded-lg shadow-sm"
            style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}
          />
        ) : (
          <img
            src={documentUrl}
            alt={filename}
            className="max-w-full max-h-full rounded-lg shadow-sm"
            style={{ transform: `scale(${zoom})` }}
          />
        )}
      </div>
    </div>
  );
}

