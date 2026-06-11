import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { TranslatePipe } from '../../core/i18n/translate.pipe';
import { RetrievedChunk } from '../../core/models';
import { IconComponent } from '../../ui/icon.component';

type LexState = { exists: boolean; building: boolean; seconds_since_build: number | null };

@Component({
  selector: 'app-laws',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IconComponent, TranslatePipe],
  templateUrl: './laws.component.html',
})
export class LawsComponent implements OnInit {
  private api = inject(ApiService);
  readonly auth = inject(AuthService);

  query = signal('');
  results = signal<RetrievedChunk[]>([]);
  loading = signal(false);
  searched = signal(false);

  // admin-only: rebuild the laws index on demand (the 168h refresh still runs automatically)
  reindexing = signal(false);
  reindexNote = signal('');
  lexState = signal<LexState | null>(null);

  ngOnInit(): void {
    if (this.auth.isAdmin()) this.refreshStatus();
  }

  async reindex(): Promise<void> {
    if (this.reindexing()) return;
    this.reindexing.set(true);
    this.reindexNote.set('');
    try {
      const r = await firstValueFrom(this.api.lexReindex());
      this.reindexNote.set(r.started ? 'laws.reindex.started' : 'laws.reindex.already');
    } catch {
      this.reindexNote.set('laws.reindex.failed');
    } finally {
      this.reindexing.set(false);
      this.pollStatus();  // watch the build to completion and reflect it in the status line
    }
  }

  private async refreshStatus(): Promise<void> {
    try { this.lexState.set(await firstValueFrom(this.api.lexStatus())); } catch { /* ignore */ }
  }

  /** Poll the index status until the build stops (or we give up after ~3 min). */
  private pollStatus(tries = 12): void {
    void this.refreshStatus().then(() => {
      if (this.lexState()?.building && tries > 0) {
        setTimeout(() => this.pollStatus(tries - 1), 15000);
      }
    });
  }

  /** Coarse "time since last successful build" for the status line. */
  ageLabel(): string {
    const s = this.lexState()?.seconds_since_build;
    if (s == null) return '';
    if (s < 90) return `${Math.round(s)}s`;
    if (s < 5400) return `${Math.round(s / 60)}m`;
    if (s < 172800) return `${Math.round(s / 3600)}h`;
    return `${Math.round(s / 86400)}d`;
  }

  onInput(e: Event): void { this.query.set((e.target as HTMLInputElement).value); }
  onKey(e: KeyboardEvent): void { if (e.key === 'Enter') this.run(); }

  async run(): Promise<void> {
    const q = this.query().trim();
    if (!q || this.loading()) return;
    this.loading.set(true);
    try {
      const res = await firstValueFrom(this.api.retrieveLaws(q, 8));
      this.results.set(res.chunks);
    } catch {
      this.results.set([]);
    } finally {
      this.loading.set(false);
      this.searched.set(true);
    }
  }

  url(c: RetrievedChunk): string | null {
    const u = c.metadata?.['url'];
    return typeof u === 'string' && u ? u : null;
  }

  pct(score: number): number { return Math.round(score * 100); }
}
