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
  document_type: 'invoice' | 'purchase_order' | 'receipt' | 'po';
  document_number: string;
  reference_number?: string; // Legacy field, maps to document_number
  vendor_name?: string;
  total_amount?: number;
  currency: string;
  status: string;
  document_date?: string;
  date?: string; // Legacy field, maps to document_date
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

  finalize: async (id: number): Promise<{ success: boolean; document_id: number; status: string; message: string }> => {
    const response = await api.post(`/api/documents/${id}/finalize`);
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

// Matching API interfaces
export interface MatchingIssueV2 {
  category: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  details: Record<string, any>;
  line_number?: number;
}

export interface MatchingResultV2 {
  id: string;
  invoice_id: number;
  po_id?: number;
  match_status: 'matched' | 'needs_review';
  confidence_score?: number;
  issues?: MatchingIssueV2[];
  reasoning?: string;
  matched_by?: string;
  matched_at: string;
  reviewed_by?: string;
  reviewed_at?: string;
  created_at: string;
  invoice_number?: string;
  vendor_name?: string;
  total_amount?: number;
  currency?: string;
}

export interface ReviewQueueItem {
  id: string;
  matching_result_id: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  issue_category: string;
  assigned_to?: string;
  sla_deadline?: string;
  created_at: string;
  resolved_at?: string;
  resolution_notes?: string;
  matching_result?: MatchingResultV2;
}

export const matchingApi = {
  processInvoice: async (invoiceId: number): Promise<MatchingResultV2> => {
    const response = await api.post(`/api/matching/${invoiceId}/process`);
    return response.data;
  },

  getResult: async (resultId: string): Promise<MatchingResultV2> => {
    const response = await api.get(`/api/matching/results/${resultId}`);
    return response.data;
  },

  listReviewQueue: async (params?: {
    priority?: string;
    issue_category?: string;
    status?: 'pending' | 'resolved';
    limit?: number;
  }): Promise<ReviewQueueItem[]> => {
    const response = await api.get('/api/matching/review-queue', { params });
    return response.data;
  },

  resolveQueueItem: async (
    queueId: string,
    resolution: 'approved' | 'rejected',
    notes?: string
  ): Promise<ReviewQueueItem> => {
    const response = await api.post(`/api/matching/review-queue/${queueId}/resolve`, {
      resolution,
      notes,
    });
    return response.data;
  },

  batchProcess: async (invoiceIds: number[]): Promise<{
    processed_count: number;
    results: MatchingResultV2[];
    errors: Array<{ invoice_id: number; error: string }>;
  }> => {
    const response = await api.post('/api/matching/batch', {
      invoice_ids: invoiceIds,
    });
    return response.data;
  },
};

// Document Pairs API interfaces
export type WorkflowStage = 'uploaded' | 'extracted' | 'matched' | 'validated' | 'approved';
export type PairStatus = 'in_progress' | 'needs_review' | 'approved' | 'rejected';

export interface StageTimestamps {
  uploaded?: string;
  extracted?: string;
  matched?: string;
  validated?: string;
  approved?: string;
}

export interface ValidationIssue {
  id: string;
  category: string;
  severity: 'critical' | 'warning' | 'info';
  field?: string;
  description: string;
  invoice_value?: any;
  po_value?: any;
  suggestion?: string;
  resolved: boolean;
  resolved_by?: string;
  resolved_at?: string;
  resolution_action?: string;
  resolution_notes?: string;
  created_at: string;
}

export interface DocumentPairSummary {
  id: string;
  invoice_id: number;
  po_id?: number;
  invoice_number: string;
  po_number?: string;
  vendor_name?: string;
  total_amount?: number;
  current_stage: WorkflowStage;
  overall_status: PairStatus;
  requires_review: boolean;
  issue_count: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentPairDetail extends DocumentPairSummary {
  invoice: InvoiceDetail;
  purchase_order?: PurchaseOrder;
  matching_result?: MatchingResultV2;
  validation_issues: ValidationIssue[];
  stage_timestamps: StageTimestamps;
  confidence_score?: number;
  reasoning?: string;
}

export interface FieldComparison {
  field_name: string;
  invoice_value: any;
  po_value: any;
  match: boolean;
  similarity?: number;
  diff_explanation?: string;
  severity?: string;
}

export interface LineItemComparison {
  line_number: number;
  invoice_line?: Record<string, any>;
  po_line?: Record<string, any>;
  field_comparisons: FieldComparison[];
  overall_match: 'perfect' | 'partial' | 'mismatch' | 'missing';
  issues: ValidationIssue[];
}

export interface TimelineEntry {
  timestamp: string;
  event_type: string;
  description: string;
  actor?: string;
  details?: Record<string, any>;
}

export const pairsApi = {
  list: async (params?: {
    status?: string[];
    stage?: string[];
    has_issues?: boolean;
    vendor?: string;
    limit?: number;
    offset?: number;
  }): Promise<DocumentPairSummary[]> => {
    const response = await api.get('/api/matching/pairs', { params });
    return response.data;
  },

  getById: async (pairId: string): Promise<DocumentPairDetail> => {
    const response = await api.get(`/api/matching/pairs/${pairId}`);
    return response.data;
  },

  getComparison: async (pairId: string): Promise<LineItemComparison[]> => {
    const response = await api.get(`/api/matching/pairs/${pairId}/comparison`);
    return response.data;
  },

  getTimeline: async (pairId: string): Promise<TimelineEntry[]> => {
    const response = await api.get(`/api/matching/pairs/${pairId}/timeline`);
    return response.data;
  },

  resolveIssue: async (
    pairId: string,
    issueId: string,
    resolution: 'accepted' | 'overridden' | 'corrected',
    notes?: string
  ): Promise<ValidationIssue> => {
    const response = await api.post(
      `/api/matching/pairs/${pairId}/issues/${issueId}/resolve`,
      {
        resolution_action: resolution,
        notes,
      }
    );
    return response.data;
  },

  advanceStage: async (pairId: string): Promise<DocumentPairDetail> => {
    const response = await api.post(`/api/matching/pairs/${pairId}/advance`);
    return response.data;
  },

  approve: async (pairId: string, notes?: string): Promise<DocumentPairDetail> => {
    const response = await api.post(`/api/matching/pairs/${pairId}/approve`, {
      notes,
    });
    return response.data;
  },

  reject: async (pairId: string, reason: string): Promise<DocumentPairDetail> => {
    const response = await api.post(`/api/matching/pairs/${pairId}/reject`, {
      notes: reason,
    });
    return response.data;
  },
};

// Email API types and functions
export interface EmailDraftRequest {
  document_pair_id: string;
  issue_ids?: string[];
}

export interface EmailDraftResponse {
  email_log_id: string;
  to_addresses: string[];
  cc_addresses?: string[];
  subject: string;
  body_text: string;
  body_html: string;
  summary: string;
  status: string;
}

export interface EmailSendRequest {
  email_log_id: string;
  subject?: string;
  body_text?: string;
  body_html?: string;
  to_addresses?: string[];
  cc_addresses?: string[];
}

export interface EmailSendResponse {
  email_log_id: string;
  message_id: string;
  thread_id?: string;
  success: boolean;
  status: string;
  error_message?: string;
}

export interface EmailLog {
  id: string;
  document_pair_id: string;
  to_addresses: string[];
  cc_addresses?: string[];
  subject: string;
  body_text: string;
  body_html?: string;
  issue_ids?: string[];
  status: 'draft' | 'sent' | 'failed';
  gmail_message_id?: string;
  gmail_thread_id?: string;
  drafted_at: string;
  drafted_by?: string;
  sent_at?: string;
  sent_by?: string;
  error_message?: string;
  created_at: string;
}

export const emailApi = {
  draft: async (request: EmailDraftRequest): Promise<EmailDraftResponse> => {
    const response = await api.post('/api/email/draft', request);
    return response.data;
  },

  send: async (request: EmailSendRequest): Promise<EmailSendResponse> => {
    const response = await api.post('/api/email/send', request);
    return response.data;
  },

  getPairEmails: async (pairId: string): Promise<EmailLog[]> => {
    const response = await api.get(`/api/email/pair/${pairId}/emails`);
    return response.data;
  },
};

