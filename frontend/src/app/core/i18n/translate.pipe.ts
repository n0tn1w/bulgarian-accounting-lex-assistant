import { Pipe, PipeTransform, inject } from '@angular/core';

import { I18nService } from './i18n.service';

/** `{{ 'inspector.field.number' | t }}` — impure so a language toggle re-renders the
 *  string everywhere, including inside OnPush panes. */
@Pipe({ name: 't', standalone: true, pure: false })
export class TranslatePipe implements PipeTransform {
  private i18n = inject(I18nService);

  transform(key: string, params?: Record<string, string | number>): string {
    return this.i18n.t(key, params);
  }
}
