import { Injectable, computed, effect, inject, signal } from '@angular/core';

import { ApiService } from './api.service';
import { AssistantService } from './assistant.service';
import { AuthService } from './auth.service';
import { I18nService } from './i18n/i18n.service';
import { AssistantTurn, ChatMessage, Conversation, ConvoContext } from './chat';
import { groupInvoices } from './grouping';
import { Invoice, SearchHit } from './models';

type Health = 'up' | 'down' | 'checking';
type View = 'assistant' | 'documents' | 'search' | 'laws';

let _idCounter = 0;
const newId = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${++_idCounter}`;

function emptyConversation(): Conversation {
  const now = Date.now();
  return { id: newId('c'), title: '', messages: [], activeInvoice: null, createdAt: now, updatedAt: now };
}

// Single source of truth for conversations, the per-company working set and the
// active invoice. Owns turn orchestration so chat, documents and inspector stay in sync.
@Injectable({ providedIn: 'root' })
export class WorkspaceStore {
  private assistant = inject(AssistantService);
  private api = inject(ApiService);
  private auth = inject(AuthService);
  private i18n = inject(I18nService);

  /** A short, translated title for a conversation, derived from its first user message. */
  private deriveTitle(text: string): string {
    const t = text.trim();
    const low = t.toLowerCase();
    if (t.startsWith('📎')) return t.replace('📎', '').trim().slice(0, 40) || this.i18n.t('store.title.upload');
    if (low.includes('validate') || low.includes('провер')) return this.i18n.t('store.title.validation');
    if (low.includes('duplicate') || low.includes('дубли')) return this.i18n.t('store.title.duplicate');
    if (low.includes('help') || low.includes('what can you')) return this.i18n.t('store.title.capabilities');
    if (low.includes('compan') || low.includes('фирм')) return this.i18n.t('store.title.companies');
    if (/(фактура|invoice|ддс|vat|еик|обща стойност|данъчна основа)/i.test(t)) {
      const m = t.match(/(\d{7,15})/);
      return m ? this.i18n.t('store.title.invoiceN', { number: m[1] }) : this.i18n.t('store.title.invoiceAnalysis');
    }
    const firstLine = t.split('\n')[0];
    return firstLine.length > 44 ? firstLine.slice(0, 44) + '…' : firstLine;
  }

  readonly conversations = signal<Conversation[]>([emptyConversation()]);
  readonly activeId = signal<string>(this.conversations()[0].id);

  readonly workingSet = signal<Invoice[]>([]);
  readonly busy = signal(false);
  readonly health = signal<Health>('checking');
  readonly view = signal<View>('assistant');

  // Object URLs of just-uploaded originals, keyed by invoice domain id, for instant
  // in-browser preview before the server round-trip.
  readonly localFiles = signal<Map<string, string>>(new Map());
  private lastUploadedFile: File | null = null;

  // search
  readonly searchHits = signal<SearchHit[]>([]);
  readonly searchQuery = signal('');
  readonly searching = signal(false);

  readonly sortedConversations = computed(() =>
    [...this.conversations()].sort((a, b) => b.updatedAt - a.updatedAt),
  );
  /** Most recent few for the rail; the rest live behind "Show all". */
  readonly recentConversations = computed(() => this.sortedConversations().slice(0, 8));
  readonly hasMoreConversations = computed(() => this.conversations().length > 8);
  readonly active = computed(() => this.conversations().find((c) => c.id === this.activeId()) ?? null);
  readonly messages = computed<ChatMessage[]>(() => this.active()?.messages ?? []);
  readonly activeInvoice = computed<Invoice | null>(() => this.active()?.activeInvoice ?? null);
  readonly hasConversation = computed(() => this.messages().length > 0);

  readonly invoiceCount = computed(() => this.workingSet().length);
  readonly companies = computed(() => groupInvoices(this.workingSet()));
  readonly companyCount = computed(() => this.companies().length);

  private seq = 0;
  private restored = signal(false);

  private _persist = effect(() => {
    const conversations = this.conversations();
    const activeId = this.activeId();
    const view = this.view();
    if (this.restored()) this.writeState({ conversations, activeId, view });
  });

  context(): ConvoContext {
    // Prior turns (exclude the in-flight pending reply and the current question).
    const prior = this.messages().filter((m) => !m.pending && m.text);
    if (prior.length && prior[prior.length - 1].role === 'user') prior.pop();
    return {
      activeInvoice: this.activeInvoice(),
      workingSet: this.workingSet(),
      history: prior.map((m) => ({ role: m.role, content: m.text ?? '' })),
    };
  }

  newConversation(): void {
    this.view.set('assistant');
    // Reuse an existing empty chat instead of stacking up blank "New chat" entries.
    const empty = this.conversations().find((c) => c.messages.length === 0);
    if (empty) {
      this.activeId.set(empty.id);
      return;
    }
    const conv = emptyConversation();
    this.conversations.update((list) => [conv, ...list]);
    this.activeId.set(conv.id);
  }

  selectConversation(id: string): void {
    this.activeId.set(id);
    this.view.set('assistant');
  }

  deleteConversation(id: string): void {
    this.conversations.update((list) => list.filter((c) => c.id !== id));
    if (!this.conversations().length) this.conversations.set([emptyConversation()]);
    if (this.activeId() === id) this.activeId.set(this.conversations()[0].id);
  }

  /** "New chat" alias kept for existing callers. */
  reset(): void {
    this.newConversation();
  }

  setView(v: View): void {
    this.view.set(v);
  }

  loadWorkspace(): void {
    this.restoreState();
    this.api.listWorkspaceInvoices().subscribe({
      next: (r) => this.workingSet.set(r.invoices),
      error: () => {},
    });
  }

  search(query: string): void {
    const q = query.trim();
    this.searchQuery.set(q);
    this.view.set('search');
    if (!q) {
      this.searchHits.set([]);
      return;
    }
    this.searching.set(true);
    this.api.searchInvoices(q, 12).subscribe({
      next: (r) => { this.searchHits.set(r.hits); this.searching.set(false); },
      error: () => this.searching.set(false),
    });
  }

  checkHealth(): void {
    this.health.set('checking');
    this.api.health().subscribe({
      next: () => this.health.set('up'),
      error: () => this.health.set('down'),
    });
  }

  sendText(text: string): void {
    if (!text.trim() || this.busy()) return;
    this.view.set('assistant');
    this.pushUser(text);
    this.runTurn(() => this.assistant.handleText(text, this.context()));
  }

  sendFile(file: File): void {
    if (this.busy()) return;
    this.view.set('assistant');
    this.lastUploadedFile = file;  // consumed in applyTurn to register + persist the original
    this.pushUser(`📎 ${file.name}`);
    this.runTurn(() => this.assistant.handleFile(file, this.context()));
  }

  validateInvoice(invoice: Invoice): void {
    if (this.busy()) return;
    this.setActive(invoice);
    this.sendText('validate');
  }

  findDuplicatesForInvoice(invoice: Invoice): void {
    if (this.busy()) return;
    this.setActive(invoice);
    this.view.set('assistant');
    this.pushUser(`Find duplicates of ${invoice.id}`);
    this.runTurn(() => this.assistant.duplicatesForInvoice(invoice, this.context()));
  }

  setActive(invoice: Invoice): void {
    this.updateActive((c) => ({ ...c, activeInvoice: invoice }));
  }

  readonly lookupBusy = signal(false);
  readonly trainSaved = signal<string | null>(null);

  /** Save the active (corrected) document as a labeled training example. */
  saveActiveForTraining(): void {
    const inv = this.activeInvoice();
    if (!inv) return;
    this.api.saveDocumentLabel(inv.id, inv).subscribe({
      next: () => this.trainSaved.set(inv.id),
      error: () => {},
    });
  }

  /** Flip supplier and recipient on the active invoice (manual override). */
  swapActiveParties(): void {
    const inv = this.activeInvoice();
    if (!inv) return;
    const fc = { ...inv.field_confidence };
    const swap = (a: string, b: string) => { const t = fc[a]; fc[a] = fc[b]; fc[b] = t; };
    swap('supplier_name', 'recipient_name');
    swap('supplier_vat', 'recipient_vat');
    swap('supplier_eik', 'recipient_eik');
    const perspective = inv.perspective === 'recipient' ? 'supplier' : 'recipient';
    this._setActiveInvoice({
      ...inv,
      supplier: inv.recipient,
      recipient: inv.supplier,
      perspective,
      field_confidence: fc,
    });
  }

  /** Recover/confirm a party from the register by its EIK and merge it in. */
  lookupActiveCompany(which: 'supplier' | 'recipient' = 'supplier'): void {
    const inv = this.activeInvoice();
    const party = which === 'recipient' ? inv?.recipient : inv?.supplier;
    if (!inv || !party?.eik) return;
    this.lookupBusy.set(true);
    this.api.lookupCompany(party.eik).subscribe({
      next: (r) => {
        const info = r.company;
        const merged = {
          ...party,
          name: info.name ?? party.name,
          vat_number: info.vat_number ?? party.vat_number,
          address: info.address_line1 ?? party.address,
          source: 'merged',
        };
        this._setActiveInvoice({ ...inv, [which]: merged } as Invoice);
        this.lookupBusy.set(false);
      },
      error: () => this.lookupBusy.set(false),
    });
  }

  /** Override the detected document type on the active invoice. */
  setActiveDocType(doc_type: string): void {
    const inv = this.activeInvoice();
    if (!inv || inv.doc_type === doc_type) return;
    this._setActiveInvoice({ ...inv, doc_type });
  }

  /** Update the active invoice, recomputing the displayed company from the perspective. */
  private _setActiveInvoice(inv: Invoice): void {
    const primary = inv.perspective === 'recipient' ? inv.recipient : inv.supplier;
    const company_name = primary.name || primary.vat_number || primary.eik || 'Unknown company';
    const next = { ...inv, company_name };
    this.setActive(next);
    this.workingSet.update((set) => set.map((i) => (i.id === next.id ? next : i)));
  }

  /**
   * Resolves a citation's stored-invoice id (the DB UUID that RAG cites) to the
   * full invoice and appends an 'invoice' card to the active conversation. The
   * workingSet is keyed by the invoice's *domain* id, not this UUID, so we resolve
   * server-side via /workspace/invoices/by-id. Degrades to a 'note' on failure.
   */
  openInvoice(invoiceId: string): void {
    this.api.getInvoiceById(invoiceId).subscribe({
      next: (invoice) => this._appendInvoiceCard(invoice),
      error: () => this._appendNoteCard(`Could not open invoice ${invoiceId}.`),
    });
  }

  private _appendInvoiceCard(invoice: import('./models').Invoice): void {
    const id = ++this.seq;
    this.updateActive((c) => ({
      ...c,
      messages: [
        ...c.messages,
        {
          id,
          role: 'assistant' as const,
          text: '',
          cards: [{ type: 'invoice' as const, invoice }],
          ts: Date.now(),
        },
      ],
    }));
  }

  private _appendNoteCard(text: string): void {
    const id = ++this.seq;
    this.updateActive((c) => ({
      ...c,
      messages: [
        ...c.messages,
        {
          id,
          role: 'assistant' as const,
          text: '',
          cards: [{ type: 'note' as const, tone: 'warn' as const, text }],
          ts: Date.now(),
        },
      ],
    }));
  }

  removeInvoice(id: string): void {
    this.revokeLocalFile(id);
    this.workingSet.update((set) => set.filter((i) => i.id !== id));
    this.conversations.update((list) =>
      list.map((c) => (c.activeInvoice?.id === id ? { ...c, activeInvoice: null } : c)),
    );
    if (this.auth.isAuthed()) this.api.deleteWorkspaceInvoice(id).subscribe({ error: () => {} });
  }

  clearPersisted(): void {
    const key = this.chatKey();
    if (key) localStorage.removeItem(key);
    this.restored.set(false);
    this.conversations.set([emptyConversation()]);
    this.activeId.set(this.conversations()[0].id);
    this.workingSet.set([]);
    this.localFiles().forEach((url) => URL.revokeObjectURL(url));
    this.localFiles.set(new Map());
  }

  private updateActive(fn: (c: Conversation) => Conversation): void {
    const id = this.activeId();
    this.conversations.update((list) =>
      list.map((c) => (c.id === id ? { ...fn(c), updatedAt: Date.now() } : c)),
    );
  }

  private pushUser(text: string): void {
    this.updateActive((c) => {
      const messages = [...c.messages, { id: ++this.seq, role: 'user' as const, text, cards: [], ts: Date.now() }];
      const title = c.messages.length === 0 ? this.deriveTitle(text) : c.title;
      return { ...c, messages, title };
    });
  }

  private async runTurn(fn: () => Promise<AssistantTurn>): Promise<void> {
    this.busy.set(true);
    const id = ++this.seq;
    this.updateActive((c) => ({
      ...c,
      messages: [...c.messages, { id, role: 'assistant', cards: [], ts: Date.now(), pending: true }],
    }));
    try {
      this.applyTurn(id, await fn());
    } catch (e: any) {
      this.complete(id, {
        text: '',
        cards: [{
          type: 'note',
          tone: 'warn',
          text:
            this.health() === 'down'
              ? this.i18n.t('store.error.backendDown')
              : this.i18n.t('store.error.generic', { error: e?.message ?? e }),
        }],
      });
    } finally {
      this.busy.set(false);
      this.lastUploadedFile = null;
    }
  }

  private applyTurn(id: number, turn: AssistantTurn): void {
    const file = this.lastUploadedFile;
    const active = turn.setActiveInvoice;
    if (file && active) this.registerLocalFile(active.id, file);

    if (turn.addInvoices?.length) {
      this.mergeInvoices(turn.addInvoices);
      if (this.auth.isAuthed()) {
        this.api.persistInvoices(turn.addInvoices).subscribe({
          next: () => {
            if (file && active) this.api.uploadDocumentFile(active.id, file).subscribe({ error: () => {} });
          },
          error: () => {},
        });
      }
    }
    this.updateActive((c) => ({
      ...c,
      activeInvoice: turn.setActiveInvoice ?? c.activeInvoice,
      messages: c.messages.map((m) =>
        m.id === id ? { ...m, text: turn.text, cards: turn.cards, pending: false } : m,
      ),
    }));
  }

  /** Keep an object URL for instant preview of a just-uploaded original. */
  private registerLocalFile(id: string, file: File): void {
    const url = URL.createObjectURL(file);
    this.localFiles.update((m) => {
      const prev = m.get(id);
      if (prev) URL.revokeObjectURL(prev);
      const next = new Map(m);
      next.set(id, url);
      return next;
    });
  }

  private revokeLocalFile(id: string): void {
    const url = this.localFiles().get(id);
    if (url) {
      URL.revokeObjectURL(url);
      this.localFiles.update((m) => {
        const next = new Map(m);
        next.delete(id);
        return next;
      });
    }
  }

  private complete(id: number, turn: AssistantTurn): void {
    this.updateActive((c) => ({
      ...c,
      messages: c.messages.map((m) =>
        m.id === id ? { ...m, text: turn.text, cards: turn.cards, pending: false } : m,
      ),
    }));
  }

  private mergeInvoices(invoices: Invoice[]): void {
    this.workingSet.update((set) => {
      const byId = new Map(set.map((i) => [i.id, i]));
      for (const i of invoices) byId.set(i.id, i);
      return [...byId.values()];
    });
  }

  private chatKey(): string | null {
    const u = this.auth.user();
    return u ? `ledgerly.chats.${u.tenant_id}` : null;
  }

  private restoreState(): void {
    const key = this.chatKey();
    if (key) {
      try {
        const raw = localStorage.getItem(key);
        if (raw) {
          const s = JSON.parse(raw);
          let convs: Conversation[] = Array.isArray(s.conversations) ? s.conversations : [];
          // migrate the older single-conversation format
          if (!convs.length && Array.isArray(s.messages)) {
            const c = emptyConversation();
            c.messages = s.messages;
            c.activeInvoice = s.activeInvoice ?? null;
            c.title = s.messages.length ? this.deriveTitle(s.messages.find((m: ChatMessage) => m.role === 'user')?.text ?? '') : '';
            convs = [c];
          }
          convs.forEach((c) => (c.messages = (c.messages ?? []).filter((m) => !m.pending)));
          if (convs.length) {
            this.conversations.set(convs);
            this.activeId.set(convs.some((c) => c.id === s.activeId) ? s.activeId : convs[0].id);
            this.seq = convs.reduce((mx, c) => c.messages.reduce((m2, msg) => Math.max(m2, msg.id), mx), 0);
            if (s.view) this.view.set(s.view);
          }
        }
      } catch {
        /* ignore corrupt storage */
      }
    }
    this.restored.set(true);
  }

  private writeState(state: { conversations: Conversation[]; activeId: string; view: View }): void {
    const key = this.chatKey();
    if (!key) return;
    try {
      localStorage.setItem(key, JSON.stringify(state));
    } catch {
      /* storage full / unavailable */
    }
  }
}
