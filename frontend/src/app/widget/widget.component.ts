import { ChangeDetectionStrategy, Component, ElementRef, Input, inject } from '@angular/core';

import { ApiConfig } from '../core/api.service';
import { WorkspaceStore } from '../core/workspace.store';
import { ChatComponent } from '../features/chat/chat.component';
import { IconComponent } from '../ui/icon.component';

// Compact, self-contained assistant embedded via Angular Elements as
// <ledgerly-assistant>. Reuses the same chat surface and store as the full app.
// Point it at a backend with the api-base attribute, e.g.
//   <ledgerly-assistant api-base="https://api.yourdomain.eu"></ledgerly-assistant>
@Component({
  selector: 'ledgerly-widget-root',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ChatComponent, IconComponent],
  template: `
    <div class="widget">
      <header class="pane-head">
        <span class="brand-mark" style="background:var(--pine);color:var(--pine-ink);width:30px;height:30px">
          <app-icon name="ledger" [size]="17" [weight]="1.7" />
        </span>
        <span class="pane-title" style="font-size:16px">Ledgerly</span>
        <span class="chip" style="margin-left:auto">
          <span class="dot" style="position:static;box-shadow:none"
            [class.up]="store.health() === 'up'" [class.down]="store.health() === 'down'"
            [class.wait]="store.health() === 'checking'"></span>
          {{ store.health() === 'up' ? 'online' : store.health() === 'down' ? 'offline' : '…' }}
        </span>
      </header>
      <app-chat />
    </div>
  `,
})
export class WidgetComponent {
  readonly store = inject(WorkspaceStore);
  private cfg = inject(ApiConfig);
  private host = inject(ElementRef<HTMLElement>);

  @Input() set apiBase(v: string) { if (v) this.cfg.base = v; }

  constructor() {
    // pick up the attribute even if Angular Elements hasn't mapped the input yet
    const attr = this.host.nativeElement.getAttribute('api-base');
    if (attr) this.cfg.base = attr;
    this.store.checkHealth();
  }
}
