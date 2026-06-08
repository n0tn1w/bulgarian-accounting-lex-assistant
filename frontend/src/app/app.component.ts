import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';

import { AuthService } from './core/auth.service';
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
  ],
  templateUrl: './app.component.html',
})
export class AppComponent {
  readonly auth = inject(AuthService);
  readonly store = inject(WorkspaceStore);
  locale = signal<'bg' | 'en'>('bg');
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

  title(): string {
    switch (this.store.view()) {
      case 'documents': return 'Documents';
      case 'search': return 'Search';
      case 'laws': return 'VAT & laws';
      default: return 'Assistant';
    }
  }

  openFile(): void {
    const sel = this.store.view() === 'documents'
      ? 'app-documents input[type=file]'
      : 'app-chat input[type=file]';
    document.querySelector<HTMLInputElement>(sel)?.click();
  }
}
