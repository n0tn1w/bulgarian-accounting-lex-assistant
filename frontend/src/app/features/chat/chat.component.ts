import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  effect,
  inject,
  signal,
  viewChild,
} from '@angular/core';

import { I18nService } from '../../core/i18n/i18n.service';
import { TranslatePipe } from '../../core/i18n/translate.pipe';
import { WorkspaceStore } from '../../core/workspace.store';
import { CardViewComponent } from '../cards/card-view.component';
import { FormatPipe } from '../../ui/format.pipe';
import { IconComponent } from '../../ui/icon.component';

interface Starter { icon: string; titleKey: string; descKey: string; action: () => void; }

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
  imports: [CardViewComponent, IconComponent, FormatPipe, TranslatePipe],
  templateUrl: './chat.component.html',
})
export class ChatComponent {
  readonly store = inject(WorkspaceStore);
  private i18n = inject(I18nService);

  draft = signal('');
  focused = signal(false);
  dragging = signal(false);

  private threadEl = viewChild<ElementRef<HTMLElement>>('thread');
  private fileEl = viewChild<ElementRef<HTMLInputElement>>('file');

  starters: Starter[] = [
    { icon: 'spark', titleKey: 'chat.starter.sample.title', descKey: 'chat.starter.sample.desc',
      action: () => this.store.sendText(SAMPLE_INVOICE) },
    { icon: 'check', titleKey: 'chat.starter.validate.title', descKey: 'chat.starter.validate.desc',
      action: () => this.store.sendText('validate') },
    { icon: 'scale', titleKey: 'chat.starter.duplicates.title', descKey: 'chat.starter.duplicates.desc',
      action: () => this.store.sendText('find duplicates') },
    { icon: 'shield', titleKey: 'chat.starter.law.title', descKey: 'chat.starter.law.desc',
      action: () => this.store.sendText(this.i18n.t('chat.starter.law.prompt')) },
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
    const files = Array.from(input.files ?? []);
    if (files.length) this.store.sendFiles(files);
    input.value = '';
  }

  onDrop(e: DragEvent): void {
    e.preventDefault();
    this.dragging.set(false);
    const files = Array.from(e.dataTransfer?.files ?? []);
    if (files.length) this.store.sendFiles(files);
  }

  onDragOver(e: DragEvent): void { e.preventDefault(); this.dragging.set(true); }
  onDragLeave(): void { this.dragging.set(false); }
}
