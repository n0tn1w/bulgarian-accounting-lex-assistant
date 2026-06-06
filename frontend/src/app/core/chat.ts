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
  | { type: 'note'; tone: 'info' | 'warn'; text: string };

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
