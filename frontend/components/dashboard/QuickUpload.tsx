import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Upload } from 'lucide-react';

interface QuickUploadProps {
  onUpload: () => void;
}

export default function QuickUpload({ onUpload }: QuickUploadProps) {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center justify-center py-12">
        <div className="rounded-full bg-primary/10 p-4 mb-4">
          <Upload className="h-8 w-8 text-primary" />
        </div>
        <h3 className="text-lg font-semibold mb-2">Upload Document</h3>
        <p className="text-sm text-muted-foreground text-center mb-6 max-w-md">
          Upload invoices, purchase orders, or receipts to start processing
        </p>
        <Button onClick={onUpload} size="lg" className="gap-2">
          <Upload className="h-4 w-4" />
          Choose File
        </Button>
      </CardContent>
    </Card>
  );
}

