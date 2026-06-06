import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  effect,
  inject,
  signal,
  viewChild,
} from '@angular/core';

import { WorkspaceStore } from '../../core/workspace.store';
import { CardViewComponent } from '../cards/card-view.component';
import { FormatPipe } from '../../ui/format.pipe';
import { IconComponent } from '../../ui/icon.component';

interface Starter { icon: string; title: string; desc: string; action: () => void; }

const SAMPLE_INVOICE = `ФАКТУРА № 2000002487
Дата: 15.03.2025
Доставчик: ТРИЕРА ЕООД
ЕИК: 820194079
ДДС № BG820194079
Получател: ДЕМО ООД
Данъчна основа: 16 143,38
Размер на данъка: 3 228,68
Обща стойност: 19 372,06`;

@Component({
  selector: 'app-chat',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CardViewComponent, IconComponent, FormatPipe],
  templateUrl: './chat.component.html',
})
export class ChatComponent {
  readonly store = inject(WorkspaceStore);

  draft = signal('');
  focused = signal(false);
  dragging = signal(false);

  private threadEl = viewChild<ElementRef<HTMLElement>>('thread');
  private fileEl = viewChild<ElementRef<HTMLInputElement>>('file');

  starters: Starter[] = [
    { icon: 'spark', title: 'Analyze a sample invoice', desc: 'Extract fields, score confidence and validate.',
      action: () => this.store.sendText(SAMPLE_INVOICE) },
    { icon: 'check', title: 'Validate fields & VAT', desc: 'Arithmetic, VAT rate, VAT/EIK format, completeness.',
      action: () => this.store.sendText('validate') },
    { icon: 'scale', title: 'Detect duplicates', desc: 'Compare an invoice across an uploaded batch.',
      action: () => this.store.sendText('find duplicates') },
    { icon: 'shield', title: 'Ask about VAT & law', desc: 'Grounded in Bulgarian legislation with citations.',
      action: () => this.store.sendText('Каква е ставката на ДДС и в какъв срок се издава фактура?') },
  ];

  constructor() {
    // Keep the thread pinned to the latest message.
    effect(() => {
      this.store.messages();
      const el = this.threadEl()?.nativeElement;
      if (el) queueMicrotask(() => (el.scrollTop = el.scrollHeight));
    });
  }

  send(): void {
    const text = this.draft().trim();
    if (!text) return;
    this.store.sendText(text);
    this.draft.set('');
  }

  onInput(e: Event): void {
    const ta = e.target as HTMLTextAreaElement;
    this.draft.set(ta.value);
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px';
  }

  onKeydown(e: KeyboardEvent): void {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      this.send();
    }
  }

  openFile(): void { this.fileEl()?.nativeElement.click(); }

  onFile(e: Event): void {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) this.store.sendFile(file);
    input.value = '';
  }

  onDrop(e: DragEvent): void {
    e.preventDefault();
    this.dragging.set(false);
    const file = e.dataTransfer?.files?.[0];
    if (file) this.store.sendFile(file);
  }

  onDragOver(e: DragEvent): void { e.preventDefault(); this.dragging.set(true); }
  onDragLeave(): void { this.dragging.set(false); }
}
