import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

/** Inline stroke-icon set. Usage: <app-icon name="send" /> */
const PATHS: Record<string, string> = {
  ledger: 'M5 4v16M5 8h11M5 12h11M5 16h7 M19 15.5a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0',
  send: 'M7 11l9-7-4 16-2.5-6.5L7 11z',
  paperclip: 'M21 11l-8.5 8.5a4 4 0 0 1-5.7-5.7L14 6.4a2.5 2.5 0 0 1 3.6 3.6l-7.3 7.3a1 1 0 0 1-1.4-1.4l6.6-6.6',
  spark: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z',
  check: 'M5 12.5l4 4 10-10',
  alert: 'M12 8v5M12 16.5v.5M10.3 4.3l-7 12A2 2 0 0 0 5 19.5h14a2 2 0 0 0 1.7-3.2l-7-12a2 2 0 0 0-3.4 0z',
  x: 'M6 6l12 12M18 6L6 18',
  file: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5zM14 3v5h5',
  search: 'M11 19a8 8 0 1 1 0-16 8 8 0 0 1 0 16zM21 21l-4.3-4.3',
  shield: 'M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z',
  globe: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c2.5 2.6 2.5 15.4 0 18M12 3c-2.5 2.6-2.5 15.4 0 18',
  plus: 'M12 5v14M5 12h14',
  scale: 'M12 4v16M7 8h10M6 8l-3 6h6l-3-6zM18 8l-3 6h6l-3-6z',
  doc: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5zM9 13h6M9 17h4',
  bolt: 'M13 3L5 13h5l-1 8 8-10h-5l1-8z',
  chat: 'M21 12a8 8 0 0 1-11.5 7.2L4 21l1.8-5.5A8 8 0 1 1 21 12z',
};

@Component({
  selector: 'app-icon',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<svg [attr.width]="size" [attr.height]="size" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" [attr.stroke-width]="weight" stroke-linecap="round" stroke-linejoin="round"
    aria-hidden="true"><path [attr.d]="d" /></svg>`,
})
export class IconComponent {
  @Input({ required: true }) name!: string;
  @Input() size = 18;
  @Input() weight = 1.8;
  get d(): string { return PATHS[this.name] ?? ''; }
}
