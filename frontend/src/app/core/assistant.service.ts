import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { ApiService } from './api.service';
import { I18nService } from './i18n/i18n.service';
import { AssistantTurn, ChatCard, ConvoContext } from './chat';
import { groupInvoices } from './grouping';
import { DocCandidate, Invoice, TextUnit, docHasAmounts, docTypeLabel, extraLabelKey } from './models';

// Client-side conversation handling: routes the user's intent to the backend
// tools (extract/validate/duplicates) and composes a grounded reply. Collapses
// into a single /chat call once the chat orchestrator is wired up.
@Injectable({ providedIn: 'root' })
export class AssistantService {
  private api = inject(ApiService);
  private i18n = inject(I18nService);
  private t = (k: string, p?: Record<string, string | number>) => this.i18n.t(k, p);

  async handleText(input: string, ctx: ConvoContext): Promise<AssistantTurn> {
    const text = input.trim();
    const lower = text.toLowerCase();

    if (!text) return this.fallback();
    if (text.startsWith('<') && text.includes('>')) return this.ingestXml(text);

    if (/\b(validate|check|verify|провер)/.test(lower)) {
      if (!ctx.activeInvoice) {
        return this.note(this.t('assistant.note.addInvoiceValidate'));
      }
      return this.runValidation(ctx.activeInvoice);
    }

    if (/\b(duplicate|dupe|dedup|дубли)/.test(lower)) {
      if (!ctx.activeInvoice) {
        return this.note(this.t('assistant.note.addInvoiceDuplicates'));
      }
      return this.duplicatesForInvoice(ctx.activeInvoice, ctx);
    }

    if (/\b(compan|group|firm|фирм|контраг)/.test(lower)) {
      return this.companiesOverview(ctx);
    }

    if (/\b(help|what can you|capabilities)/.test(lower)) return this.help();
    if (this.looksLikeInvoice(text)) return this.ingestText(text);
    // everything else is a grounded question for the chat orchestrator
    // (invoices RAG + laws RAG into the LLM)
    return this.askLLM(text, ctx);
  }

  // Explicit question → straight to the chat orchestrator, bypassing handleText's
  // pasted-invoice heuristic. The inspector's grounded prompts mention invoice fields
  // and would otherwise be misrouted to extraction instead of answered by the LLM.
  ask(message: string, ctx: ConvoContext): Promise<AssistantTurn> {
    return this.askLLM(message, ctx);
  }

  // Free-form question via /chat (both RAGs + the LLM), rendered with sources.
  private async askLLM(message: string, ctx: ConvoContext): Promise<AssistantTurn> {
    try {
      const res = await firstValueFrom(
        this.api.chat(message, ctx.history, ctx.activeInvoice?.company_key ?? null),
      );
      const cards: ChatCard[] = (res.cards as ChatCard[] | undefined)?.length
        ? (res.cards as ChatCard[])
        : res.citations?.length
          ? [{ type: 'sources', citations: res.citations, model: res.model }]
          : [];
      return { text: res.reply, cards };
    } catch {
      return this.note(this.t('assistant.note.modelUnreachable'), 'warn');
    }
  }

  async handleFile(file: File, ctx: ConvoContext, vision = true): Promise<AssistantTurn> {
    const name = file.name.toLowerCase();
    if (name.endsWith('.xml') || file.type.includes('xml')) {
      return this.ingestXml(await file.text(), file.name.replace(/\.[^.]+$/, ''));
    }
    if (name.endsWith('.pdf') || file.type === 'application/pdf') {
      try {
        const res = await firstValueFrom(this.api.extractPdf(file, 'auto', vision));
        return this.afterExtract(res.invoice, this.t('assistant.read', { name: file.name }));
      } catch (e: any) {
        if (e?.status === 503) {
          return this.note(this.t('assistant.note.ocrDisabled'), 'warn');
        }
        return this.note(this.t('assistant.note.pdfError', { error: e?.message ?? e }), 'warn');
      }
    }
    if (/\.(jpe?g|png|tiff?|webp|heic|bmp)$/.test(name) || file.type.startsWith('image/')) {
      try {
        const res = await firstValueFrom(this.api.extractImage(file, 'auto', vision));
        return this.afterExtract(res.invoice, this.t('assistant.read', { name: file.name }));
      } catch (e: any) {
        if (e?.status === 503) {
          return this.note(this.t('assistant.note.ocrDisabled'), 'warn');
        }
        return this.note(this.t('assistant.note.pdfError', { error: e?.message ?? e }), 'warn');
      }
    }
    if (name.endsWith('.txt') || file.type.startsWith('text/')) return this.ingestText(await file.text());
    return this.note(this.t('assistant.note.unsupported', { name: file.name }), 'warn');
  }

  private async ingestXml(xml: string, label = 'upload'): Promise<AssistantTurn> {
    const res = await firstValueFrom(this.api.extractXml(xml, label));
    const invoices = res.invoices;
    if (!invoices.length) {
      return this.note(this.t('assistant.note.xmlNoRecords'), 'warn');
    }
    return {
      text: this.t('assistant.parsedXml', { n: invoices.length, m: res.groups.length }),
      cards: [{ type: 'companies', groups: res.groups }],
      addInvoices: invoices,
    };
  }

  private async ingestText(text: string): Promise<AssistantTurn> {
    const res = await firstValueFrom(this.api.extractText(text, this.makeId('inv')));
    return this.afterExtract(res.invoice, this.t('assistant.extracted'));
  }

  private async afterExtract(invoice: Invoice, lead: string): Promise<AssistantTurn> {
    const cards: ChatCard[] = [{ type: 'invoice', invoice }];
    const type = this.t(docTypeLabel(invoice.doc_type));
    let summary = lead + this.t('assistant.docFor', { type, company: invoice.company_name || '—' });

    if (docHasAmounts(invoice.doc_type)) {
      const v = await firstValueFrom(this.api.validate(invoice));
      const failed = v.results.filter((r) => !r.passed);
      summary += v.is_valid ? this.t('assistant.passes') : this.t('assistant.issues', { count: failed.length });
      const low = Object.entries(invoice.field_confidence)
        .filter(([, c]) => c > 0 && c < 0.7)
        .map(([f]) => f);
      if (low.length) summary += this.t('assistant.lowConf', { fields: low.join(', ') });
      cards.push({ type: 'validation', invoiceId: invoice.id, isValid: v.is_valid, results: v.results });
    } else {
      const extras = Object.entries(invoice.extra ?? {})
        .slice(0, 3)
        .map(([k, val]) => `${this.t(extraLabelKey(k))}: ${val}`);
      if (extras.length) summary += ` ${extras.join(' · ')}.`;
    }

    return { text: summary, cards, setActiveInvoice: invoice, addInvoices: [invoice] };
  }

  private async runValidation(invoice: Invoice): Promise<AssistantTurn> {
    const v = await firstValueFrom(this.api.validate(invoice));
    const failed = v.results.filter((r) => !r.passed).length;
    return {
      text: v.is_valid
        ? this.t('assistant.validatePass', { id: invoice.id })
        : this.t('assistant.validateIssues', { id: invoice.id, count: failed }),
      cards: [{ type: 'validation', invoiceId: invoice.id, isValid: v.is_valid, results: v.results }],
    };
  }

  /** Duplicates scoped to the invoice's own company working set. */
  async duplicatesForInvoice(invoice: Invoice, ctx: ConvoContext): Promise<AssistantTurn> {
    const sameCompany = ctx.workingSet.filter(
      (i) => i.id !== invoice.id && (i.company_key ?? 'unknown') === (invoice.company_key ?? 'unknown'),
    );
    const company = invoice.company_name || '—';
    if (!sameCompany.length) {
      return this.note(this.t('assistant.dupNothing', { company }));
    }
    const query = invoiceToDoc(invoice);
    const candidates = sameCompany.map(invoiceToDoc);
    const res = await firstValueFrom(this.api.duplicates(query, candidates, 5));
    const dupes = res.matches.filter((m) => m.is_duplicate).length;
    return {
      text: dupes
        ? this.t('assistant.dupFound', { count: dupes, id: invoice.id, company })
        : this.t('assistant.dupNone', { id: invoice.id, company }),
      cards: [{ type: 'duplicates', queryId: invoice.id, matches: res.matches }],
    };
  }

  private companiesOverview(ctx: ConvoContext): AssistantTurn {
    if (!ctx.workingSet.length) {
      return this.note(this.t('assistant.note.noCompanies'));
    }
    return {
      text: this.t('assistant.companiesOverview'),
      cards: [{ type: 'companies', groups: groupInvoices(ctx.workingSet) }],
    };
  }

  private help(): AssistantTurn {
    return { text: this.t('assistant.help'), cards: [] };
  }

  private fallback(): AssistantTurn {
    return { text: this.t('assistant.fallback'), cards: [] };
  }

  private note(text: string, tone: 'info' | 'warn' = 'info'): AssistantTurn {
    return { text: '', cards: [{ type: 'note', tone, text }] };
  }

  private looksLikeInvoice(text: string): boolean {
    return text.length > 24 && /(фактура|invoice|ддс|vat|еик|обща стойност|данъчна основа|total)/i.test(text);
  }

  private makeId(prefix: string): string {
    return `${prefix}-${Date.now().toString(36)}`;
  }
}

/** Project an Invoice to a DocCandidate for the comparison engine. */
export function invoiceToDoc(inv: Invoice): DocCandidate {
  const units: TextUnit[] = [];
  const add = (field: string, value?: string | null) => {
    if (value != null && value !== '') {
      units.push({ kind: 'fieldName', text: field });
      units.push({ kind: 'value', text: String(value) });
    }
  };
  add('invoiceNumber', inv.number);
  add('documentDate', inv.date);
  add('supplierName', inv.supplier?.name);
  add('supplierVAT', inv.supplier?.vat_number);
  add('supplierEIK', inv.supplier?.eik);
  add('recipientName', inv.recipient?.name);
  add('netAmount', inv.net_amount);
  add('totalAmount', inv.total_amount);
  return { id: inv.id, units };
}
