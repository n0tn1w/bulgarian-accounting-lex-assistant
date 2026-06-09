import { ChangeDetectionStrategy, Component, OnDestroy, effect, inject, input, signal } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

import { ApiService } from '../core/api.service';
import { TranslatePipe } from '../core/i18n/translate.pipe';
import { WorkspaceStore } from '../core/workspace.store';
import { IconComponent } from './icon.component';

/** Previews the original uploaded document. Prefers the in-session object URL (instant,
 *  no round-trip); otherwise fetches the persisted file as a Blob — the auth interceptor
 *  attaches the token, so we cannot just point an <iframe> at the URL. The inline frame is
 *  small (the inspector is narrow), so an expand-to-fullscreen and open-in-new-tab are
 *  offered for actually reading the document. */
@Component({
  selector: 'app-pdf-viewer',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, IconComponent],
  template: `
    @if (safeUrl(); as url) {
      <div class="pdf-bar">
        <button class="icon-btn" [title]="'inspector.preview.expand' | t" (click)="expanded.set(true)">
          <app-icon name="search" [size]="15" />
        </button>
        <button class="icon-btn" [title]="'inspector.preview.newTab' | t" (click)="openNewTab()">
          <app-icon name="doc" [size]="15" />
        </button>
      </div>
      <iframe class="pdf-frame" [src]="url" title="Original document"></iframe>

      @if (expanded()) {
        <div class="modal-backdrop" (click)="expanded.set(false)">
          <div class="pdf-modal" (click)="$event.stopPropagation()">
            <button class="icon-btn pdf-modal-close" [title]="'inspector.preview.hide' | t"
                    (click)="expanded.set(false)"><app-icon name="x" [size]="18" /></button>
            <iframe class="pdf-modal-frame" [src]="url" title="Original document"></iframe>
          </div>
        </div>
      }
    } @else if (loading()) {
      <div class="typing" style="justify-content:center; padding:24px"><i></i><i></i><i></i></div>
    } @else {
      <div class="faint" style="padding:14px; font-size:13px">{{ 'inspector.preview.none' | t }}</div>
    }
  `,
})
export class PdfViewerComponent implements OnDestroy {
  externalId = input.required<string>();

  private store = inject(WorkspaceStore);
  private api = inject(ApiService);
  private san = inject(DomSanitizer);

  safeUrl = signal<SafeResourceUrl | null>(null);
  loading = signal(false);
  expanded = signal(false);
  private rawUrl: string | null = null;
  private blobUrl: string | null = null;

  constructor() {
    effect(() => {
      const id = this.externalId();
      this.revoke();
      this.safeUrl.set(null);
      this.expanded.set(false);
      const local = this.store.localFiles().get(id);
      if (local) {
        this.rawUrl = local;
        this.safeUrl.set(this.san.bypassSecurityTrustResourceUrl(local));
        return;
      }
      this.loading.set(true);
      this.api.getDocumentFile(id).subscribe({
        next: (b) => { this.setBlob(b); this.loading.set(false); },
        error: () => this.loading.set(false),
      });
    });
  }

  openNewTab(): void {
    if (this.rawUrl) window.open(this.rawUrl, '_blank', 'noopener');
  }

  private setBlob(b: Blob): void {
    this.blobUrl = URL.createObjectURL(b);
    this.rawUrl = this.blobUrl;
    this.safeUrl.set(this.san.bypassSecurityTrustResourceUrl(this.blobUrl));
  }

  // Only revoke URLs this component created; the store owns the localFiles URLs.
  private revoke(): void {
    if (this.blobUrl) {
      URL.revokeObjectURL(this.blobUrl);
      this.blobUrl = null;
    }
    this.rawUrl = null;
  }

  ngOnDestroy(): void {
    this.revoke();
  }
}
