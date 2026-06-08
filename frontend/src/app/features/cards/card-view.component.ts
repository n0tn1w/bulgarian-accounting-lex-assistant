import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';

import { ChatCard } from '../../core/chat';
import { Invoice } from '../../core/models';
import { IconComponent } from '../../ui/icon.component';
import { MeterComponent } from '../../ui/meter.component';
import { MoneyPipe } from '../../ui/money.pipe';

@Component({
  selector: 'app-card-view',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IconComponent, MeterComponent, MoneyPipe],
  templateUrl: './card-view.component.html',
})
export class CardViewComponent {
  @Input({ required: true }) card!: ChatCard;

  /** Emits the invoice_id (UUID) when the user clicks a cited chip or invoice row. */
  @Output() openInvoice = new EventEmitter<string>();

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
