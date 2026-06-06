import { ChangeDetectionStrategy, Component, ElementRef, inject, signal, viewChild } from '@angular/core';

import { WorkspaceStore } from '../../core/workspace.store';
import { Invoice } from '../../core/models';
import { IconComponent } from '../../ui/icon.component';
import { MoneyPipe } from '../../ui/money.pipe';

@Component({
  selector: 'app-documents',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IconComponent, MoneyPipe],
  templateUrl: './documents.component.html',
})
export class DocumentsComponent {
  readonly store = inject(WorkspaceStore);
  dragging = signal(false);
  private fileEl = viewChild<ElementRef<HTMLInputElement>>('file');

  avgConf(inv: Invoice): number | null {
    const vals = Object.values(inv.field_confidence).filter((c) => c > 0);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  }
  pct(n: number | null): string { return n == null ? '' : `${Math.round(n * 100)}%`; }

  openFile(): void { this.fileEl()?.nativeElement.click(); }
  onFile(e: Event): void {
    const input = e.target as HTMLInputElement;
    const f = input.files?.[0];
    if (f) this.store.sendFile(f);
    input.value = '';
  }
  onDrop(e: DragEvent): void {
    e.preventDefault();
    this.dragging.set(false);
    const f = e.dataTransfer?.files?.[0];
    if (f) this.store.sendFile(f);
  }
  onDragOver(e: DragEvent): void { e.preventDefault(); this.dragging.set(true); }
  onDragLeave(): void { this.dragging.set(false); }
}
