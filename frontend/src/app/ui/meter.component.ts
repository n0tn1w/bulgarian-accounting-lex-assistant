import { ChangeDetectionStrategy, Component, Input, computed, signal } from '@angular/core';

/** Confidence meter: a small animated bar coloured by confidence band. */
@Component({
  selector: 'app-meter',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="meter" [title]="'confidence ' + pct()">
      <span class="track"><span class="fill" [style.width.%]="value * 100" [style.background]="color()"></span></span>
      <span class="pct">{{ pct() }}</span>
    </span>
  `,
})
export class MeterComponent {
  private _v = signal(0);
  @Input({ required: true }) set value(v: number) { this._v.set(v ?? 0); }
  get value(): number { return this._v(); }

  pct = computed(() => `${Math.round(this._v() * 100)}%`);
  color = computed(() => {
    const v = this._v();
    if (v >= 0.8) return 'var(--ok)';
    if (v >= 0.5) return 'var(--ochre)';
    return 'var(--err)';
  });
}
