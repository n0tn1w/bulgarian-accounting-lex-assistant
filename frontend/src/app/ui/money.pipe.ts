import { Pipe, PipeTransform } from '@angular/core';

/** Format a Decimal-as-string amount with grouped, tabular-friendly digits. */
@Pipe({ name: 'money', standalone: true })
export class MoneyPipe implements PipeTransform {
  transform(value: string | number | null | undefined, currency = 'BGN'): string {
    if (value === null || value === undefined || value === '') return '—';
    const n = typeof value === 'number' ? value : Number(value);
    if (Number.isNaN(n)) return String(value);
    const formatted = new Intl.NumberFormat('bg-BG', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(n);
    return `${formatted} ${currency}`;
  }
}
