// @ts-ignore - axios types are included in the package
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  // Don't set default Content-Type - set it per request type
  // File uploads need multipart/form-data, JSON requests need application/json
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
      headers: {},
      maxContentLength: Infinity,
      maxBodyLength: Infinity,
    });
    return response.data;
  },

  approve: async (id: number, reason?: string): Promise<void> => {
    await api.post(`/api/invoices/${id}/approve`, {
      decision: 'approved',
      reason,
      user_identifier: 'manager@example.com',
    }, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
  },

  reject: async (id: number, reason: string): Promise<void> => {
    await api.post(`/api/invoices/${id}/reject`, {
      decision: 'rejected',
      reason,
      user_identifier: 'manager@example.com',
    }, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
  },

  route: async (id: number, reason: string): Promise<void> => {
    await api.post(`/api/invoices/${id}/route`, {
      decision: 'routed',
      reason,
      user_identifier: 'manager@example.com',
    }, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
  },
};

export interface POCreate {
  po_number: string;
  vendor_id: number;
  currency?: string;
  status?: string;
  requester_email?: string;
  po_lines: POLineCreate[];
}

export interface POLineCreate {
  line_no: number;
  sku?: string;
  description: string;
  quantity: number;
  unit_price: number;
}

export interface POList {
  id: number;
  po_number: string;
  vendor_id: number;
  vendor_name?: string;
  total_amount: number;
  currency: string;
  status: string;
  created_at: string;
}

export const poApi = {
  list: async (params?: { vendor_id?: number; status?: string; skip?: number; limit?: number }): Promise<POList[]> => {
    const response = await api.get('/api/purchase-orders', { params });
    return response.data;
  },

  get: async (poNumber: string): Promise<PurchaseOrder> => {
    const response = await api.get(`/api/purchase-orders/${poNumber}`);
    return response.data;
  },

  create: async (po: POCreate): Promise<PurchaseOrder> => {
    const response = await api.post('/api/purchase-orders', po, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.data;
  },
};

export const vendorApi = {
  list: async (): Promise<any[]> => {
    const response = await api.get('/api/vendors');
    return response.data;
  },
};

// Document Queue Types
export interface Document {
  id: number;
  filename: string;
  file_path: string;
  document_type: 'invoice' | 'purchase_order' | 'receipt' | null;
  status: 'uploaded' | 'classified' | 'ocr_processing' | 'pending_verification' | 'verified' | 'processed' | 'error' | 'pending' | 'processing';
  error_message?: string;
  ocr_data?: any;
  vendor_name?: string;
  vendor_id?: number;
  document_number?: string;
  document_date?: string;
  total_amount?: number;
  currency?: string;
  type_specific_data?: any;
  line_items?: any[];
  vendor_match?: any;
  created_at: string;
  updated_at?: string;
  uploaded_at?: string;
  processed_at?: string;
}

export interface DocumentOCRResult {
  id: number;
  status: string;
  ocr_data?: any;
  error_message?: string;
}

export interface InvoiceSaveData {
  invoice_number: string;
  vendor_name?: string;
  vendor_id?: number;
  po_number?: string;
  invoice_date?: string;
  total_amount?: number;
  currency?: string;
  line_items?: {
    line_no: number;
    sku?: string;
    description: string;
    quantity: number;
    unit_price: number;
  }[];
}

export interface POSaveData {
  po_number: string;
  vendor_name?: string;
  vendor_id?: number;
  order_date?: string;
  total_amount: number;
  currency?: string;
  requester_email?: string;
  po_lines?: {
    line_no: number;
    sku?: string;
    description: string;
    quantity: number;
    unit_price: number;
  }[];
}

export interface ProcessedDocument {
  id: number;
  document_type: 'invoice' | 'po';
  reference_number: string;
  vendor_name?: string;
  total_amount?: number;
  currency: string;
  status: string;
  date?: string;
  source_document_id?: number;
  created_at: string;
}

export const documentApi = {
  list: async (status?: string): Promise<Document[]> => {
    const params = status ? { status } : {};
    const response = await api.get('/api/documents', { params });
    return response.data;
  },

  get: async (id: number): Promise<Document> => {
    const response = await api.get(`/api/documents/${id}`);
    return response.data;
  },

  upload: async (file: File): Promise<Document> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/api/documents', formData, {
      headers: {},
      maxContentLength: Infinity,
      maxBodyLength: Infinity,
    });
    return response.data;
  },

  setType: async (id: number, documentType: 'invoice' | 'purchase_order' | 'receipt'): Promise<Document> => {
    const response = await api.post(`/api/documents/${id}/classify`, {
      document_type: documentType,
    }, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.data;
  },

  process: async (id: number): Promise<DocumentOCRResult> => {
    const response = await api.post(`/api/documents/${id}/process-ocr`);
    return response.data;
  },

  retry: async (id: number): Promise<DocumentOCRResult> => {
    const response = await api.post(`/api/documents/${id}/retry`);
    return response.data;
  },

  save: async (id: number, data: {
    vendor_name?: string;
    vendor_id?: number;
    document_number: string;
    document_date?: string;
    total_amount?: number;
    currency?: string;
    line_items?: any[];
    invoice_data?: {
      po_number?: string;
      payment_terms?: string;
      due_date?: string;
      tax_amount?: number;
    };
    po_data?: {
      requester_name?: string;
      requester_email?: string;
      ship_to_address?: string;
      order_date?: string;
    };
    receipt_data?: {
      merchant_name?: string;
      payment_method?: string;
      transaction_id?: string;
    };
  }): Promise<Document> => {
    const response = await api.post(`/api/documents/${id}/verify`, data, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/documents/${id}`);
  },

  listProcessed: async (documentType?: string): Promise<ProcessedDocument[]> => {
    const params = documentType ? { document_type: documentType } : {};
    const response = await api.get('/api/documents/processed/all', { params });
    return response.data;
  },
};

// Agent API Types
export interface AgentTask {
  task_id: string;
  invoice_id: number;
  task_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'escalated';
  confidence_score?: number;
  reasoning?: string;
  resolution_action?: string;
  applied: boolean;
  created_at: string;
  completed_at?: string;
  error_message?: string;
  output_data?: any;
}

export const agentApi = {
  resolve: async (invoiceId: number): Promise<AgentTask> => {
    const response = await api.post(`/api/agents/resolve?invoice_id=${invoiceId}`);
    return response.data;
  },

  getTask: async (taskId: string): Promise<AgentTask> => {
    const response = await api.get(`/api/agents/tasks/${taskId}`);
    return response.data;
  },

  getInvoiceTasks: async (invoiceId: number): Promise<AgentTask[]> => {
    const response = await api.get(`/api/agents/tasks/invoice/${invoiceId}`);
    return response.data;
  },
};

