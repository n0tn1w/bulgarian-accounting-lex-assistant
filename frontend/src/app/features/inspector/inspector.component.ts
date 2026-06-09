import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { I18nService } from '../../core/i18n/i18n.service';
import { TranslatePipe } from '../../core/i18n/translate.pipe';
import { Invoice, Party, docHasAmounts, extraLabelKey } from '../../core/models';
import { WorkspaceStore } from '../../core/workspace.store';
import { IconComponent } from '../../ui/icon.component';
import { MoneyPipe } from '../../ui/money.pipe';
import { PdfViewerComponent } from '../../ui/pdf-viewer.component';

interface DocType { value: string; labelKey: string; }
interface Suggestion { labelKey: string; promptKey: string; }

@Component({
  selector: 'app-inspector',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IconComponent, MoneyPipe, TranslatePipe, PdfViewerComponent],
  templateUrl: './inspector.component.html',
})
export class InspectorComponent {
  readonly store = inject(WorkspaceStore);
  private i18n = inject(I18nService);

  showPreview = signal(false);
  togglePreview(): void { this.showPreview.update((v) => !v); }

  // mean confidence over tracked fields
  avgConfidence = computed(() => {
    const inv = this.store.activeInvoice();
    if (!inv) return null;
    const vals = Object.values(inv.field_confidence).filter((c) => c > 0);
    if (!vals.length) return null;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  });

  // Document types the backend can classify; labels are translated in the template.
  readonly DOC_TYPES: DocType[] = [
    'invoice', 'credit_note', 'debit_note', 'proforma', 'simplified_invoice', 'protocol',
    'fiscal_receipt', 'customs_declaration', 'bank_statement', 'goods_receipt',
    'expense_report', 'other',
  ].map((value) => ({ value, labelKey: `docType.${value}` }));

  extraKey = extraLabelKey;

  pct(n: number | null): string {
    return n == null ? '—' : `${Math.round(n * 100)}%`;
  }

  /** Whether a party's fields were filled or corrected from the register. */
  recovered(p: Party): boolean {
    return p?.source === 'register' || p?.source === 'merged';
  }

  /** Type-specific fields (IBAN, fiscal device, MRN, ...) for display. */
  extras(inv: Invoice): [string, string][] {
    return Object.entries(inv.extra ?? {});
  }

  onDocType(ev: Event): void {
    this.store.setActiveDocType((ev.target as HTMLSelectElement).value);
  }

  /** Documents with monetary totals support the arithmetic Validate / Duplicates checks. */
  hasAmounts(inv: Invoice): boolean {
    return docHasAmounts(inv.doc_type);
  }

  /** Send a suggested action's prompt in the active language. */
  runSuggested(promptKey: string): void {
    this.store.sendText(this.i18n.t(promptKey));
  }

  /** Actions proposed for the document, tailored to its type. */
  suggestedActions(inv: Invoice): Suggestion[] {
    switch (inv.doc_type) {
      case 'fiscal_receipt':
        return [{ labelKey: 'suggest.fiscal.label', promptKey: 'suggest.fiscal.prompt' }];
      case 'bank_statement':
        return [{ labelKey: 'suggest.bank.label', promptKey: 'suggest.bank.prompt' }];
      case 'customs_declaration':
        return [{ labelKey: 'suggest.customs.label', promptKey: 'suggest.customs.prompt' }];
      case 'protocol':
      case 'expense_report':
        return [{ labelKey: 'suggest.reverseCharge.label', promptKey: 'suggest.reverseCharge.prompt' }];
      case 'credit_note':
      case 'debit_note':
        return [{ labelKey: 'suggest.creditDebit.label', promptKey: 'suggest.creditDebit.prompt' }];
      default:
        return [{ labelKey: 'suggest.vat.label', promptKey: 'suggest.vat.prompt' }];
    }
  }
}
