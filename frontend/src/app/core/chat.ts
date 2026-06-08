import { CompanyGroup, DuplicateMatch, Invoice, ValidationResult } from './models';

export interface Citation {
  id: string;
  source: string;
  kind: string;
}

export type ChatCard =
  | { type: 'invoice'; invoice: Invoice }
  | { type: 'validation'; invoiceId: string; isValid: boolean; results: ValidationResult[] }
  | { type: 'duplicates'; queryId: string; matches: DuplicateMatch[] }
  | { type: 'companies'; groups: CompanyGroup[] }
  | { type: 'sources'; citations: Citation[]; model: string }
  | { type: 'note'; tone: 'info' | 'warn'; text: string }
  | { type: 'sum'; total_amount: number; total_net?: number; total_vat?: number;
      currency?: string | null; count: number;
      groups: { key: string; total: number; count: number }[] }
  | { type: 'comparison'; metric: string; value_a: number; value_b: number;
      delta: number; pct_change?: number | null }
  | { type: 'invoices'; items: { invoice_id: string; number?: string | null;
      vendor_name?: string | null; date?: string | null;
      total_amount?: number | null; currency?: string | null; score?: number | null }[] };

export interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  text?: string;
  cards: ChatCard[];
  ts: number;
  pending?: boolean;
}

/** Result of the assistant handling one turn. */
export interface AssistantTurn {
  text: string;
  cards: ChatCard[];
  setActiveInvoice?: Invoice;
  addInvoices?: Invoice[];
}

export interface ConvoContext {
  activeInvoice: Invoice | null;
  workingSet: Invoice[];
  history: { role: 'user' | 'assistant'; content: string }[];
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  activeInvoice: Invoice | null;
  createdAt: number;
  updatedAt: number;
}
