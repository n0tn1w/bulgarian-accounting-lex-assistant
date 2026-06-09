import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';

import { TranslatePipe } from '../../core/i18n/translate.pipe';
import { ChatCard } from '../../core/chat';
import { Invoice, docTypeLabel, extraLabelKey } from '../../core/models';
import { IconComponent } from '../../ui/icon.component';
import { MeterComponent } from '../../ui/meter.component';
import { MoneyPipe } from '../../ui/money.pipe';

@Component({
  selector: 'app-card-view',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IconComponent, MeterComponent, MoneyPipe, TranslatePipe],
  templateUrl: './card-view.component.html',
})
export class CardViewComponent {
  @Input({ required: true }) card!: ChatCard;

  /** Emits the invoice_id (UUID) when the user clicks a cited chip or invoice row. */
  @Output() openInvoice = new EventEmitter<string>();

  /** i18n key for the document type label (Invoice, Customs declaration, ...). */
  docLabel = docTypeLabel;
  extraKey = extraLabelKey;

  /** Which per-type layout to render for this document. */
  effectiveDocType(inv: Invoice): 'customs' | 'bank' | 'fiscal' | 'invoice' | 'generic' {
    switch (inv.doc_type) {
      case 'customs_declaration': return 'customs';
      case 'bank_statement': return 'bank';
      case 'fiscal_receipt': return 'fiscal';
      case 'goods_receipt':
      case 'other': return 'generic';
      default: return 'invoice'; // invoice / credit_note / debit_note / proforma / simplified / protocol / expense
    }
  }

  /** Type-specific fields (IBAN, balances, MRN, ...) as [key, value] pairs. */
  extras(inv: Invoice): [string, string][] {
    return Object.entries(inv.extra ?? {});
  }

  ex(inv: Invoice, key: string): string | null {
    return inv.extra?.[key] ?? null;
  }

  /** Confidence for a field key, or null when not tracked / zero. */
  conf(inv: Invoice, key: string): number | null {
    const c = inv.field_confidence?.[key];
    return c && c > 0 ? c : null;
  }

  pct(n: number): number { return Math.round(n * 100); }

  /** Stroke colour for a duplicate score ring. */
  ringColor(score: number): string {
    if (score >= 0.85) return 'var(--err)';
    if (score >= 0.6) return 'var(--ochre)';
    return 'var(--ink-faint)';
  }

  badgeClass(passed: boolean, severity: string): string {
    if (passed) return 'ok';
    return severity; // 'warning' | 'error' | 'info'
  }

  ruleClass(passed: boolean, severity: string): string {
    if (passed) return 'pass';
    return severity === 'error' ? 'fail' : 'warn';
  }
}
