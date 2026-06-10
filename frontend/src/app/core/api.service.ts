import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  ChatApiResponse,
  CompanyLookupResponse,
  DocCandidate,
  DuplicatesResponse,
  ExtractXmlResponse,
  GroupResponse,
  HealthResponse,
  Invoice,
  InvoiceResponse,
  RetrieveResponse,
  SearchResponse,
  TokenResponse,
  ValidateResponse,
  WorkspaceInvoicesResponse,
} from './models';

// Mutable backend base URL. Defaults to localhost; the standalone app or the
// embeddable widget can override it (from a <ledgerly-assistant api-base>
// attribute or window.__LEDGERLY_API_BASE__).
@Injectable({ providedIn: 'root' })
export class ApiConfig {
  base: string = (globalThis as any).__LEDGERLY_API_BASE__ ?? '/api';
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private cfg = inject(ApiConfig);

  private get base(): string { return this.cfg.base.replace(/\/$/, ''); }

  health(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>(`${this.base}/health`);
  }

  extractXml(xml: string, label = ''): Observable<ExtractXmlResponse> {
    return this.http.post<ExtractXmlResponse>(`${this.base}/documents/extract-xml`, { xml, label });
  }

  extractText(text: string, doc_id = 'invoice', source = 'manual', perspective = 'auto'): Observable<InvoiceResponse> {
    return this.http.post<InvoiceResponse>(`${this.base}/documents/extract-text`, { text, doc_id, source, perspective });
  }

  extractPdf(file: File, perspective = 'auto', vision = true): Observable<InvoiceResponse> {
    const form = new FormData();
    form.append('file', file, file.name);
    form.append('perspective', perspective);
    form.append('vision', String(vision));  // bulk uploads pass false to skip the slow vision fallback
    return this.http.post<InvoiceResponse>(`${this.base}/documents/extract-pdf`, form);
  }

  extractImage(file: File, perspective = 'auto', vision = true): Observable<InvoiceResponse> {
    const form = new FormData();
    form.append('file', file, file.name);
    form.append('perspective', perspective);
    form.append('vision', String(vision));
    return this.http.post<InvoiceResponse>(`${this.base}/documents/extract-image`, form);
  }

  /** Look up a counterparty in the commercial register by EIK. */
  lookupCompany(eik: string): Observable<CompanyLookupResponse> {
    return this.http.get<CompanyLookupResponse>(`${this.base}/documents/company/${encodeURIComponent(eik)}`);
  }

  /** Persist the original uploaded file for a document (tenant-scoped, auth required). */
  uploadDocumentFile(externalId: string, file: File): Observable<{ id: string; size: number }> {
    const form = new FormData();
    form.append('file', file, file.name);
    return this.http.post<{ id: string; size: number }>(
      `${this.base}/workspace/documents/${encodeURIComponent(externalId)}/file`, form);
  }

  /** external_ids of documents whose original file is stored server-side. */
  listDocumentFiles(): Observable<{ external_ids: string[] }> {
    return this.http.get<{ external_ids: string[] }>(`${this.base}/workspace/documents/files`);
  }

  /** Fetch the stored original file as a Blob (the auth interceptor adds the token). */
  getDocumentFile(externalId: string): Observable<Blob> {
    return this.http.get(`${this.base}/workspace/documents/${encodeURIComponent(externalId)}/file`,
      { responseType: 'blob' });
  }

  /** Save the (corrected) document as a labeled training example (opt-in on the server). */
  saveDocumentLabel(externalId: string, invoice: Invoice): Observable<{ saved: string }> {
    return this.http.post<{ saved: string }>(
      `${this.base}/workspace/documents/${encodeURIComponent(externalId)}/label`, invoice);
  }

  validate(invoice: Invoice): Observable<ValidateResponse> {
    return this.http.post<ValidateResponse>(`${this.base}/validate`, invoice);
  }

  duplicates(query: DocCandidate, candidates: DocCandidate[], top_k = 5): Observable<DuplicatesResponse> {
    return this.http.post<DuplicatesResponse>(`${this.base}/compare/duplicates`, { query, candidates, top_k });
  }

  // auth
  register(email: string, password: string, tenant_name: string): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(`${this.base}/auth/register`, { email, password, tenant_name });
  }
  login(email: string, password: string): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(`${this.base}/auth/login`, { email, password });
  }
  me(): Observable<TokenResponse['user']> {
    return this.http.get<TokenResponse['user']>(`${this.base}/auth/me`);
  }

  // persistent workspace (auth required)
  persistInvoices(invoices: Invoice[]): Observable<{ stored: number }> {
    return this.http.post<{ stored: number }>(`${this.base}/workspace/invoices`, { invoices });
  }
  listWorkspaceInvoices(): Observable<WorkspaceInvoicesResponse> {
    return this.http.get<WorkspaceInvoicesResponse>(`${this.base}/workspace/invoices`);
  }
  /** Resolve a citation's stored-invoice id (DB UUID) to the full invoice. */
  getInvoiceById(id: string): Observable<Invoice> {
    return this.http.get<Invoice>(`${this.base}/workspace/invoices/by-id/${encodeURIComponent(id)}`);
  }
  workspaceCompanies(): Observable<GroupResponse> {
    return this.http.get<GroupResponse>(`${this.base}/workspace/companies`);
  }
  searchInvoices(query: string, top_k = 10, company_key?: string | null): Observable<SearchResponse> {
    return this.http.post<SearchResponse>(`${this.base}/workspace/search`, { query, top_k, company_key });
  }
  deleteWorkspaceInvoice(externalId: string): Observable<{ deleted: number }> {
    return this.http.delete<{ deleted: number }>(`${this.base}/workspace/invoices/${encodeURIComponent(externalId)}`);
  }

  // chat (both RAGs into the LLM)
  chat(
    message: string,
    history: { role: string; content: string }[],
    company_key?: string | null,
  ): Observable<ChatApiResponse> {
    return this.http.post<ChatApiResponse>(`${this.base}/chat`, { message, history, company_key, top_k: 6 });
  }

  // laws RAG (lex): retrieve cited law passages
  retrieveLaws(query: string, top_k = 8): Observable<RetrieveResponse> {
    return this.http.post<RetrieveResponse>(`${this.base}/rag/laws/retrieve`, { query, top_k });
  }
}
