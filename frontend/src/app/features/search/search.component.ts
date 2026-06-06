import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';

import { WorkspaceStore } from '../../core/workspace.store';
import { CardViewComponent } from '../cards/card-view.component';
import { IconComponent } from '../../ui/icon.component';

@Component({
  selector: 'app-search',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CardViewComponent, IconComponent],
  templateUrl: './search.component.html',
})
export class SearchComponent {
  readonly store = inject(WorkspaceStore);
  query = signal('');

  onInput(e: Event): void { this.query.set((e.target as HTMLInputElement).value); }
  onKey(e: KeyboardEvent): void { if (e.key === 'Enter') this.run(); }
  run(): void { this.store.search(this.query()); }
  pct(score: number): number { return Math.round(score * 100); }
}
