import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';

import { WorkspaceStore } from '../../core/workspace.store';
import { IconComponent } from '../../ui/icon.component';
import { MoneyPipe } from '../../ui/money.pipe';

@Component({
  selector: 'app-inspector',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IconComponent, MoneyPipe],
  templateUrl: './inspector.component.html',
})
export class InspectorComponent {
  readonly store = inject(WorkspaceStore);

  // mean confidence over tracked fields
  avgConfidence = computed(() => {
    const inv = this.store.activeInvoice();
    if (!inv) return null;
    const vals = Object.values(inv.field_confidence).filter((c) => c > 0);
    if (!vals.length) return null;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  });

  pct(n: number | null): string {
    return n == null ? '—' : `${Math.round(n * 100)}%`;
  }
}
