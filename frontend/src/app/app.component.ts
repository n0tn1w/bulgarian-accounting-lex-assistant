import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';

import { AuthService } from './core/auth.service';
import { I18nService } from './core/i18n/i18n.service';
import { TranslatePipe } from './core/i18n/translate.pipe';
import { WorkspaceStore } from './core/workspace.store';
import { AuthComponent } from './features/auth/auth.component';
import { ChatComponent } from './features/chat/chat.component';
import { DocumentsComponent } from './features/documents/documents.component';
import { InspectorComponent } from './features/inspector/inspector.component';
import { LawsComponent } from './features/laws/laws.component';
import { SearchComponent } from './features/search/search.component';
import { IconComponent } from './ui/icon.component';

@Component({
  selector: 'app-root',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    AuthComponent,
    ChatComponent,
    DocumentsComponent,
    LawsComponent,
    SearchComponent,
    InspectorComponent,
    IconComponent,
    TranslatePipe,
  ],
  templateUrl: './app.component.html',
})
export class AppComponent {
  readonly auth = inject(AuthService);
  readonly store = inject(WorkspaceStore);
  readonly i18n = inject(I18nService);
  private loaded = false;

  constructor() {
    this.store.checkHealth();
    this.auth.restore();
    // load/clear the persisted working set as auth state changes
    effect(() => {
      if (this.auth.isAuthed()) {
        if (!this.loaded) {
          this.loaded = true;
          this.store.loadWorkspace();
        }
      } else {
        this.loaded = false;
      }
    });
  }

  // show-all-chats popup + delete confirmation
  showAllChats = signal(false);
  confirmDeleteId = signal<string | null>(null);

  openAllChats(): void { this.showAllChats.set(true); }
  closeAllChats(): void { this.showAllChats.set(false); this.confirmDeleteId.set(null); }
  pickConversation(id: string): void { this.store.selectConversation(id); this.closeAllChats(); }
  askDelete(id: string, e: Event): void { e.stopPropagation(); this.confirmDeleteId.set(id); }
  cancelDelete(): void { this.confirmDeleteId.set(null); }
  confirmDelete(): void {
    const id = this.confirmDeleteId();
    if (id) this.store.deleteConversation(id);
    this.confirmDeleteId.set(null);
  }
  convDate(ts: number): string {
    return new Date(ts).toLocaleDateString('bg-BG', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  logout(): void {
    this.store.clearPersisted();
    this.auth.logout();
  }

  /** i18n key for the current pane title (translated in the template). */
  titleKey(): string {
    switch (this.store.view()) {
      case 'documents': return 'app.pane.documents';
      case 'search': return 'app.pane.search';
      case 'laws': return 'app.pane.laws';
      default: return 'app.pane.assistant';
    }
  }

  /** i18n key for the backend health line. */
  statusKey(): string {
    const h = this.store.health();
    return h === 'up' ? 'app.status.up' : h === 'down' ? 'app.status.down' : 'app.status.checking';
  }

  openFile(): void {
    const sel = this.store.view() === 'documents'
      ? 'app-documents input[type=file]'
      : 'app-chat input[type=file]';
    document.querySelector<HTMLInputElement>(sel)?.click();
  }
}
