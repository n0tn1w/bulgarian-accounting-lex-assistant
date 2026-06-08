import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { RetrievedChunk } from '../../core/models';
import { IconComponent } from '../../ui/icon.component';

@Component({
  selector: 'app-laws',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IconComponent],
  templateUrl: './laws.component.html',
})
export class LawsComponent {
  private api = inject(ApiService);

  query = signal('');
  results = signal<RetrievedChunk[]>([]);
  loading = signal(false);
  searched = signal(false);

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
