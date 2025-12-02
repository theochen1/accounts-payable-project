'use client';

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { documentApi } from '@/lib/api';
import { useToast } from '@/components/ui/use-toast';
import { Upload, X, FileText, Loader2 } from 'lucide-react';
import LoadingSpinner from '@/components/shared/LoadingSpinner';

interface UploadModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

export default function UploadModal({ open, onOpenChange, onSuccess }: UploadModalProps) {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const { toast } = useToast();

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    // Validate file type
    const validTypes = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png'];
    if (!validTypes.includes(file.type)) {
      toast({
        title: 'Invalid file type',
        description: 'Please upload a PDF, JPG, or PNG file.',
        variant: 'destructive',
      });
      return;
    }

    setUploading(true);
    setUploadProgress(0);

    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 200);

      await documentApi.upload(file);
      
      clearInterval(progressInterval);
      setUploadProgress(100);

      toast({
        title: 'Upload successful',
        description: 'Your document has been uploaded and is ready for processing.',
      });

      setTimeout(() => {
        setUploading(false);
        setUploadProgress(0);
        onOpenChange(false);
        onSuccess?.();
      }, 500);
    } catch (error: any) {
      toast({
        title: 'Upload failed',
        description: error.message || 'Failed to upload document. Please try again.',
        variant: 'destructive',
      });
      setUploading(false);
      setUploadProgress(0);
    }
  }, [toast, onOpenChange, onSuccess]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
    },
    maxFiles: 1,
    disabled: uploading,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Upload Document</DialogTitle>
          <DialogDescription>
            Upload a PDF, JPG, or PNG file to start processing
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4">
          {uploading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
              <p className="text-sm text-muted-foreground mb-2">Uploading...</p>
              <div className="w-full bg-muted rounded-full h-2 mt-4">
                <div
                  className="bg-primary h-2 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground mt-2">{uploadProgress}%</p>
            </div>
          ) : (
            <div
              {...getRootProps()}
              className={`
                border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors
                ${isDragActive ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'}
              `}
            >
              <input {...getInputProps()} />
              <div className="flex flex-col items-center gap-4">
                <div className="rounded-full bg-primary/10 p-4">
                  <Upload className="h-8 w-8 text-primary" />
                </div>
                {isDragActive ? (
                  <div>
                    <p className="text-sm font-medium text-foreground">Drop file here</p>
                  </div>
                ) : (
                  <div>
                    <p className="text-sm font-medium text-foreground mb-1">
                      Drag & drop a file here
                    </p>
                    <p className="text-xs text-muted-foreground">or click to browse</p>
                    <p className="text-xs text-muted-foreground mt-2">
                      PDF, JPG, PNG up to 10MB
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

