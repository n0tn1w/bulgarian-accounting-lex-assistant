/** TypeScript mirrors of the backend domain models (see backend/app/domain/models.py).
 *  Decimal amounts are serialized by the API as strings. */

export interface TextUnit {
  kind: 'fieldName' | 'value' | 'context';
  text: string;
}

export interface DocCandidate {
  id: string;
  units: TextUnit[];
}

export interface Party {
  name?: string | null;
  vat_number?: string | null;
  eik?: string | null;
  address?: string | null;
}

export interface LineItem {
  description?: string | null;
  quantity?: string | null;
  unit_price?: string | null;
  amount?: string | null;
}

export interface TaxLine {
  rate: string;
  base?: string | null;
  amount?: string | null;
}

export interface Invoice {
  id: string;
  source: string;
  number?: string | null;
  date?: string | null;
  currency: string;
  supplier: Party;
  recipient: Party;
  line_items: LineItem[];
  tax_lines: TaxLine[];
  net_amount?: string | null;
  vat_amount?: string | null;
  total_amount?: string | null;
  field_confidence: Record<string, number>;
  company_key?: string | null;
  company_name?: string | null;
}

export interface Company {
  key: string;
  name?: string | null;
  vat?: string | null;
  eik?: string | null;
  invoice_count: number;
}

export interface CompanyGroup {
  company: Company;
  invoices: Invoice[];
}

export type Severity = 'info' | 'warning' | 'error';

export interface ValidationResult {
  rule_id: string;
  passed: boolean;
  severity: Severity;
  message: string;
  evidence: Record<string, string>;
}

export interface MatchEvidence {
  word_similarity: number;
  char_similarity: number;
  fused_score: number;
}

export interface DuplicateMatch {
  candidate_id: string;
  score: number;
  is_duplicate: boolean;
  evidence: MatchEvidence;
}

export interface AuthUser {
  id: string;
  email: string;
  role: string;
  tenant_id: string;
  tenant_name: string;
}

export interface SearchHit {
  invoice: Invoice;
  score: number;
}

// API envelopes
export interface ExtractXmlResponse {
  documents: DocCandidate[];
  invoices: Invoice[];
  groups: CompanyGroup[];
}
export interface InvoiceResponse { invoice: Invoice; }
export interface ValidateResponse { invoice_id: string; results: ValidationResult[]; is_valid: boolean; }
export interface DuplicatesResponse { matches: DuplicateMatch[]; }
export interface HealthResponse { status: string; version: string; ocr: Record<string, unknown>; }
export interface TokenResponse { access_token: string; token_type: string; user: AuthUser; }
export interface WorkspaceInvoicesResponse { invoices: Invoice[]; }
export interface GroupResponse { groups: CompanyGroup[]; }
export interface SearchResponse { hits: SearchHit[]; }

export interface ChatApiCitation { id: string; source: string; kind: string; }
export interface ChatApiResponse {
  reply: string;
  citations: ChatApiCitation[];
  model: string;
  cards?: any[];       // agent cards (ChatCard-shaped from the backend)
  refused?: boolean;
}
