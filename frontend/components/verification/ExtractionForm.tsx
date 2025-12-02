'use client';

import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import ConfidenceIndicator from '@/components/verification/ConfidenceIndicator';
import LineItemsTable from '@/components/verification/LineItemsTable';
import { Document, InvoiceSaveData, POSaveData, vendorApi } from '@/lib/api';
import { Loader2 } from 'lucide-react';

interface ExtractionFormProps {
  document: Document;
  onSave: (data: InvoiceSaveData | POSaveData) => void;
  onCancel: () => void;
  isSaving?: boolean;
}

const invoiceSchema = z.object({
  invoice_number: z.string().min(1, 'Invoice number is required'),
  vendor_name: z.string().optional(),
  vendor_id: z.number().optional(),
  po_number: z.string().optional(),
  invoice_date: z.string().optional(),
  total_amount: z.number().optional(),
  currency: z.string().default('USD'),
});

const poSchema = z.object({
  po_number: z.string().min(1, 'PO number is required'),
  vendor_name: z.string().optional(),
  vendor_id: z.number().optional(),
  order_date: z.string().optional(),
  total_amount: z.number().min(0, 'Total amount is required'),
  currency: z.string().default('USD'),
  requester_email: z.string().email().optional().or(z.literal('')),
});

export default function ExtractionForm({ document, onSave, onCancel, isSaving = false }: ExtractionFormProps) {
  const ocrData = document.ocr_data || {};
  const isInvoice = document.document_type === 'invoice';
  const schema = isInvoice ? invoiceSchema : poSchema;

  const [vendors, setVendors] = useState<any[]>([]);
  const [lineItems, setLineItems] = useState(ocrData.line_items || []);

  const {
    register,
    handleSubmit,
    formState: { errors },
    setValue,
    watch,
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: isInvoice
      ? {
          invoice_number: ocrData.invoice_number || '',
          vendor_name: ocrData.vendor_name || ocrData.vendor_match?.matched_vendor_name || '',
          vendor_id: ocrData.vendor_match?.matched_vendor_id || undefined,
          po_number: ocrData.po_number || '',
          invoice_date: ocrData.invoice_date || '',
          total_amount: ocrData.total_amount || undefined,
          currency: ocrData.currency || 'USD',
        }
      : {
          po_number: ocrData.po_number || '',
          vendor_name: ocrData.vendor_name || ocrData.vendor_match?.matched_vendor_name || '',
          vendor_id: ocrData.vendor_match?.matched_vendor_id || undefined,
          order_date: ocrData.order_date || '',
          total_amount: ocrData.total_amount || 0,
          currency: ocrData.currency || 'USD',
          requester_email: ocrData.requester_email || '',
        },
  });

  useEffect(() => {
    loadVendors();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [document.id]);

  const loadVendors = async () => {
    try {
      const data = await vendorApi.list();
      setVendors(data);
      
      // Auto-populate vendor_id from OCR data if vendor_match exists
      if (ocrData.vendor_match?.matched_vendor_id) {
        const matchedVendorId = ocrData.vendor_match.matched_vendor_id;
        setValue('vendor_id', matchedVendorId);
        const matchedVendor = data.find((v: any) => v.id === matchedVendorId);
        if (matchedVendor) {
          setValue('vendor_name', matchedVendor.name);
        } else if (ocrData.vendor_match.matched_vendor_name) {
          setValue('vendor_name', ocrData.vendor_match.matched_vendor_name);
        }
      }
    } catch (error) {
      console.error('Failed to load vendors:', error);
    }
  };

  const onSubmit = (data: any) => {
    const submitData = isInvoice
      ? ({ ...data, line_items: lineItems } as InvoiceSaveData)
      : ({ ...data, po_lines: lineItems } as POSaveData);
    onSave(submitData);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-4">Extracted Data</h2>
          <p className="text-sm text-muted-foreground mb-6">
            Review and edit the extracted information below.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {isInvoice ? (
            <>
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  Invoice Number <span className="text-destructive">*</span>
                </label>
                <div>
                  <Input {...register('invoice_number')} />
                  <ConfidenceIndicator confidence={ocrData.confidence?.invoice_number} />
                </div>
                {isInvoice && (errors as any).invoice_number && (
                  <p className="text-xs text-destructive">{(errors as any).invoice_number.message as string}</p>
                )}
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Invoice Date</label>
                <Input type="date" {...register('invoice_date')} />
                <ConfidenceIndicator confidence={ocrData.confidence?.invoice_date} />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Vendor</label>
                <Select
                  value={watch('vendor_id')?.toString() || ''}
                  onValueChange={(value) => {
                    const vendor = vendors.find((v) => v.id === parseInt(value));
                    setValue('vendor_id', parseInt(value));
                    if (vendor) setValue('vendor_name', vendor.name);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select vendor..." />
                  </SelectTrigger>
                  <SelectContent>
                    {vendors.map((vendor) => (
                      <SelectItem key={vendor.id} value={vendor.id.toString()}>
                        {vendor.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Vendor Name (from OCR)</label>
                <Input {...register('vendor_name')} />
                <ConfidenceIndicator confidence={ocrData.confidence?.vendor_name} />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">PO Number</label>
                <Input {...register('po_number')} />
                <ConfidenceIndicator confidence={ocrData.confidence?.po_number} />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Total Amount</label>
                <Input
                  type="number"
                  step="0.01"
                  {...register('total_amount', { valueAsNumber: true })}
                />
                <ConfidenceIndicator confidence={ocrData.confidence?.total_amount} />
              </div>
            </>
          ) : (
            <>
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  PO Number <span className="text-destructive">*</span>
                </label>
                <Input {...register('po_number')} />
                {!isInvoice && (errors as any).po_number && (
                  <p className="text-xs text-destructive">{(errors as any).po_number.message as string}</p>
                )}
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Order Date</label>
                <Input type="date" {...register('order_date')} />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Vendor</label>
                <Select
                  value={watch('vendor_id')?.toString() || ''}
                  onValueChange={(value) => {
                    const vendor = vendors.find((v) => v.id === parseInt(value));
                    setValue('vendor_id', parseInt(value));
                    if (vendor) setValue('vendor_name', vendor.name);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select vendor..." />
                  </SelectTrigger>
                  <SelectContent>
                    {vendors.map((vendor) => (
                      <SelectItem key={vendor.id} value={vendor.id.toString()}>
                        {vendor.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Vendor Name</label>
                <Input {...register('vendor_name')} />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">
                  Total Amount <span className="text-destructive">*</span>
                </label>
                <Input
                  type="number"
                  step="0.01"
                  {...register('total_amount', { valueAsNumber: true })}
                />
                {!isInvoice && (errors as any).total_amount && (
                  <p className="text-xs text-destructive">{(errors as any).total_amount.message as string}</p>
                )}
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Requester Email</label>
                <Input type="email" {...register('requester_email')} />
              </div>
            </>
          )}

          <div className="space-y-2">
            <label className="text-sm font-medium">Currency</label>
            <Select value={watch('currency')} onValueChange={(value) => setValue('currency', value)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="USD">USD</SelectItem>
                <SelectItem value="EUR">EUR</SelectItem>
                <SelectItem value="GBP">GBP</SelectItem>
                <SelectItem value="CAD">CAD</SelectItem>
                <SelectItem value="AUD">AUD</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <LineItemsTable items={lineItems} onChange={setLineItems} />
      </div>

      <div className="border-t border-border bg-background p-6 flex items-center justify-end gap-3">
        <Button type="button" variant="outline" onClick={onCancel} disabled={isSaving}>
          Cancel
        </Button>
        <Button type="submit" disabled={isSaving} className="gap-2">
          {isSaving ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            'Approve & Process'
          )}
        </Button>
      </div>
    </form>
  );
}

