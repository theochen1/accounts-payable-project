// @ts-ignore - axios types are included in the package
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface Invoice {
  id: number;
  invoice_number: string;
  vendor_id?: number;
  vendor_name?: string;
  po_number?: string;
  total_amount?: number;
  currency: string;
  status: string;
  created_at: string;
}

export interface InvoiceDetail extends Invoice {
  invoice_date?: string;
  pdf_storage_path?: string;
  ocr_json?: any;
  updated_at: string;
  invoice_lines: InvoiceLine[];
  purchase_order?: PurchaseOrder;
  matching_result?: MatchingResult;
}

export interface InvoiceLine {
  id: number;
  line_no: number;
  sku?: string;
  description: string;
  quantity: number;
  unit_price: number;
}

export interface PurchaseOrder {
  id: number;
  po_number: string;
  vendor_id: number;
  vendor_name?: string;
  total_amount: number;
  currency: string;
  status: string;
  requester_email?: string;
  created_at: string;
  updated_at: string;
  po_lines: POLine[];
}

export interface POLine {
  id: number;
  line_no: number;
  sku?: string;
  description: string;
  quantity: number;
  unit_price: number;
}

export interface MatchingResult {
  status: string;
  overall_match: boolean;
  issues: MatchingIssue[];
  line_item_matches: LineItemMatch[];
  vendor_match: boolean;
  currency_match: boolean;
  total_match: boolean;
  total_difference?: number;
  total_difference_percent?: number;
}

export interface MatchingIssue {
  type: string;
  severity: string;
  message: string;
  details?: any;
}

export interface LineItemMatch {
  invoice_line_no: number;
  po_line_no?: number;
  matched: boolean;
  issues: string[];
  invoice_sku?: string;
  po_sku?: string;
  invoice_quantity?: number;
  po_quantity?: number;
  invoice_unit_price?: number;
  po_unit_price?: number;
}

export interface DecisionCreate {
  decision: 'approved' | 'rejected' | 'routed';
  reason?: string;
  user_identifier?: string;
}

// API functions
export const invoiceApi = {
  list: async (params?: { status?: string; vendor_id?: number; skip?: number; limit?: number }): Promise<Invoice[]> => {
    const response = await api.get('/api/invoices', { params });
    return response.data;
  },

  get: async (id: number): Promise<InvoiceDetail> => {
    const response = await api.get(`/api/invoices/${id}`);
    return response.data;
  },

  upload: async (file: File): Promise<{ id: number; invoice_number: string; status: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/api/invoices/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  approve: async (id: number, reason?: string): Promise<void> => {
    await api.post(`/api/invoices/${id}/approve`, {
      decision: 'approved',
      reason,
      user_identifier: 'manager@example.com',
    });
  },

  reject: async (id: number, reason: string): Promise<void> => {
    await api.post(`/api/invoices/${id}/reject`, {
      decision: 'rejected',
      reason,
      user_identifier: 'manager@example.com',
    });
  },

  route: async (id: number, reason: string): Promise<void> => {
    await api.post(`/api/invoices/${id}/route`, {
      decision: 'routed',
      reason,
      user_identifier: 'manager@example.com',
    });
  },
};

export const poApi = {
  get: async (poNumber: string): Promise<PurchaseOrder> => {
    const response = await api.get(`/api/purchase-orders/${poNumber}`);
    return response.data;
  },
};

export const vendorApi = {
  list: async (): Promise<any[]> => {
    const response = await api.get('/api/vendors');
    return response.data;
  },
};

