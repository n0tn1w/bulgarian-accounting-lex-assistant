import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { ApiService } from './api.service';
import { AssistantTurn, ConvoContext } from './chat';
import { groupInvoices } from './grouping';
import { DocCandidate, Invoice, TextUnit } from './models';

// Client-side conversation handling: routes the user's intent to the backend
// tools (extract/validate/duplicates) and composes a grounded reply. Collapses
// into a single /chat call once the chat orchestrator is wired up.
@Injectable({ providedIn: 'root' })
export class AssistantService {
  private api = inject(ApiService);

  async handleText(input: string, ctx: ConvoContext): Promise<AssistantTurn> {
    const text = input.trim();
    const lower = text.toLowerCase();

    if (!text) return this.fallback();
    if (text.startsWith('<') && text.includes('>')) return this.ingestXml(text);

    if (/\b(validate|check|verify|провер)/.test(lower)) {
      if (!ctx.activeInvoice) {
        return this.note('Add an invoice first — paste its text, or drop an XML/PDF — then I can validate it.');
      }
      return this.runValidation(ctx.activeInvoice);
    }

    if (/\b(duplicate|dupe|dedup|дубли)/.test(lower)) {
      if (!ctx.activeInvoice) {
        return this.note('Add an invoice first, then I can search its company for duplicates.');
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

  // Free-form question via /chat (both RAGs + the LLM), rendered with sources.
  private async askLLM(message: string, ctx: ConvoContext): Promise<AssistantTurn> {
    try {
      const res = await firstValueFrom(
        this.api.chat(message, ctx.history, ctx.activeInvoice?.company_key ?? null),
      );
      const cards: AssistantTurn['cards'] = res.citations?.length
        ? [{ type: 'sources', citations: res.citations, model: res.model }]
        : [];
      return { text: res.reply, cards };
    } catch {
      return this.note('I could not reach the assistant model just now. Try again in a moment.', 'warn');
    }
  }

  async handleFile(file: File, ctx: ConvoContext): Promise<AssistantTurn> {
    const name = file.name.toLowerCase();
    if (name.endsWith('.xml') || file.type.includes('xml')) {
      return this.ingestXml(await file.text(), file.name.replace(/\.[^.]+$/, ''));
    }
    if (name.endsWith('.pdf') || file.type === 'application/pdf') {
      try {
        const res = await firstValueFrom(this.api.extractPdf(file));
        return this.afterExtract(res.invoice, `Read **${file.name}** via OCR.`);
      } catch (e: any) {
        if (e?.status === 503) {
          return this.note(
            'OCR is not enabled on the server yet (Tesseract not installed). ' +
              'You can still paste the invoice text and I will extract the fields.',
            'warn',
          );
        }
        return this.note(`Could not read that PDF: ${e?.message ?? e}`, 'warn');
      }
    }
    if (name.endsWith('.txt') || file.type.startsWith('text/')) return this.ingestText(await file.text());
    return this.note(`I can read XML, PDF and text files — "${file.name}" is not supported yet.`, 'warn');
  }

  private async ingestXml(xml: string, label = 'upload'): Promise<AssistantTurn> {
    const res = await firstValueFrom(this.api.extractXml(xml, label));
    const invoices = res.invoices;
    if (!invoices.length) {
      return this.note('I parsed the XML but found no record-like elements in it.', 'warn');
    }
    const n = invoices.length;
    const m = res.groups.length;
    return {
      text:
        `Parsed **${n}** invoice${n > 1 ? 's' : ''} across **${m}** ` +
        `compan${m > 1 ? 'ies' : 'y'} and organised them into per-company working sets. ` +
        `Open the **Documents** tab to browse, or ask me to **find duplicates**.`,
      cards: [{ type: 'companies', groups: res.groups }],
      addInvoices: invoices,
    };
  }

  private async ingestText(text: string): Promise<AssistantTurn> {
    const res = await firstValueFrom(this.api.extractText(text, this.makeId('inv')));
    return this.afterExtract(res.invoice, 'Extracted the invoice fields.');
  }

  private async afterExtract(invoice: Invoice, lead: string): Promise<AssistantTurn> {
    const v = await firstValueFrom(this.api.validate(invoice));
    const failed = v.results.filter((r) => !r.passed);
    const low = Object.entries(invoice.field_confidence)
      .filter(([, c]) => c > 0 && c < 0.7)
      .map(([f]) => f);

    let summary = `${lead} Company: **${invoice.company_name || 'unknown'}**. `;
    summary += v.is_valid
      ? 'It **passes** all blocking checks.'
      : `I found **${failed.length}** issue${failed.length > 1 ? 's' : ''} to review.`;
    if (low.length) summary += ` Low-confidence fields: ${low.join(', ')}.`;

    return {
      text: summary,
      cards: [
        { type: 'invoice', invoice },
        { type: 'validation', invoiceId: invoice.id, isValid: v.is_valid, results: v.results },
      ],
      setActiveInvoice: invoice,
      addInvoices: [invoice],
    };
  }

  private async runValidation(invoice: Invoice): Promise<AssistantTurn> {
    const v = await firstValueFrom(this.api.validate(invoice));
    const failed = v.results.filter((r) => !r.passed).length;
    return {
      text: v.is_valid
        ? `**${invoice.id}** passes all blocking checks.`
        : `**${invoice.id}** has ${failed} issue${failed > 1 ? 's' : ''}:`,
      cards: [{ type: 'validation', invoiceId: invoice.id, isValid: v.is_valid, results: v.results }],
    };
  }

  /** Duplicates scoped to the invoice's own company working set. */
  async duplicatesForInvoice(invoice: Invoice, ctx: ConvoContext): Promise<AssistantTurn> {
    const sameCompany = ctx.workingSet.filter(
      (i) => i.id !== invoice.id && (i.company_key ?? 'unknown') === (invoice.company_key ?? 'unknown'),
    );
    if (!sameCompany.length) {
      return this.note(
        `Nothing else from **${invoice.company_name || 'this company'}** to compare against yet. ` +
          `Upload more of their invoices first.`,
      );
    }
    const query = invoiceToDoc(invoice);
    const candidates = sameCompany.map(invoiceToDoc);
    const res = await firstValueFrom(this.api.duplicates(query, candidates, 5));
    const dupes = res.matches.filter((m) => m.is_duplicate).length;
    return {
      text: dupes
        ? `Found **${dupes}** likely duplicate${dupes > 1 ? 's' : ''} of **${invoice.id}** within **${invoice.company_name}**:`
        : `No duplicates of **${invoice.id}** within **${invoice.company_name}**. Closest matches:`,
      cards: [{ type: 'duplicates', queryId: invoice.id, matches: res.matches }],
    };
  }

  private companiesOverview(ctx: ConvoContext): AssistantTurn {
    if (!ctx.workingSet.length) {
      return this.note('No companies yet — upload an XML batch or some invoices first.');
    }
    return {
      text: 'Here are the companies in your working set:',
      cards: [{ type: 'companies', groups: groupInvoices(ctx.workingSet) }],
    };
  }

  private help(): AssistantTurn {
    return {
      text:
        'I work over your real documents. I can:\n' +
        '• **Extract** invoice fields from text, XML or PDF (Bulgarian + English).\n' +
        '• **Understand companies** and organise invoices into per-company working sets.\n' +
        '• **Validate** an invoice — arithmetic, VAT rate, VAT/EIK format, completeness.\n' +
        '• **Find duplicates** within a company.\n\n' +
        'Paste an invoice or drop a file to begin.',
      cards: [],
    };
  }

  private fallback(): AssistantTurn {
    return {
      text:
        "I'm grounded in your documents (full conversational reasoning arrives with the " +
        'model layer). Try pasting an invoice, dropping an XML/PDF, or asking me to ' +
        '**validate**, **find duplicates**, or show **companies**.',
      cards: [],
    };
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
