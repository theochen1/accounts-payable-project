'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { invoiceApi, InvoiceDetail } from '@/lib/api';
import InvoiceDetailView from '@/components/InvoiceDetail';
import MatchingComparison from '@/components/MatchingComparison';
import ActionButtons from '@/components/ActionButtons';

export default function InvoiceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (params.id) {
      loadInvoice(Number(params.id));
    }
  }, [params.id]);

  const loadInvoice = async (id: number) => {
    try {
      setLoading(true);
      const data = await invoiceApi.get(id);
      setInvoice(data);
    } catch (error) {
      console.error('Failed to load invoice:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (action: 'approve' | 'reject' | 'route', reason?: string) => {
    if (!invoice) return;

    try {
      if (action === 'approve') {
        await invoiceApi.approve(invoice.id, reason);
      } else if (action === 'reject') {
        if (!reason) {
          alert('Reason is required for rejection');
          return;
        }
        await invoiceApi.reject(invoice.id, reason);
      } else if (action === 'route') {
        if (!reason) {
          alert('Routing target/reason is required');
          return;
        }
        await invoiceApi.route(invoice.id, reason);
      }
      alert(`Invoice ${action}ed successfully!`);
      router.push('/');
    } catch (error: any) {
      alert(`Failed to ${action} invoice: ${error.message}`);
    }
  };

  if (loading) {
    return (
      <div className="container">
        <div>Loading...</div>
      </div>
    );
  }

  if (!invoice) {
    return (
      <div className="container">
        <div>Invoice not found</div>
      </div>
    );
  }

  return (
    <div className="container">
      <div style={{ marginBottom: '20px' }}>
        <button onClick={() => router.push('/')} className="button button-secondary">
          ← Back to Queue
        </button>
      </div>

      <InvoiceDetailView invoice={invoice} />
      {invoice.purchase_order && invoice.matching_result && (
        <MatchingComparison
          invoice={invoice}
          po={invoice.purchase_order}
          matchingResult={invoice.matching_result}
        />
      )}
      <ActionButtons invoice={invoice} onAction={handleAction} />
    </div>
  );
}

