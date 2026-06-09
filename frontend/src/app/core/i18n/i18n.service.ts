import { Injectable, computed, signal } from '@angular/core';

import { BG } from './messages.bg';
import { EN } from './messages.en';

export type Lang = 'bg' | 'en';

const STORAGE_KEY = 'ledgerly.lang';

/** Runtime translation. `lang` is a signal so anything reading through the pipe or a
 *  computed re-renders on toggle. A missing key falls back to English, then to the raw
 *  key, so the UI is never blank. Document data (law text, names, amounts) is not routed
 *  through here — only chrome. */
@Injectable({ providedIn: 'root' })
export class I18nService {
  readonly lang = signal<Lang>(this.restore());
  private readonly dict = computed(() => (this.lang() === 'bg' ? BG : EN));

  setLang(l: Lang): void {
    this.lang.set(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* storage unavailable */
    }
  }

  toggle(): void {
    this.setLang(this.lang() === 'bg' ? 'en' : 'bg');
  }

  t(key: string, params?: Record<string, string | number>): string {
    const raw = this.lookup(this.dict(), key) ?? this.lookup(EN, key);
    if (raw == null) {
      if (typeof ngDevMode !== 'undefined' && ngDevMode) {
        console.warn(`[i18n] missing key: ${key}`);
      }
      return key;
    }
    return params ? this.interpolate(raw, params) : raw;
  }

  private interpolate(str: string, params: Record<string, string | number>): string {
    return str.replace(/\{(\w+)\}/g, (_, k) => String(params[k] ?? ''));
  }

  private lookup(dict: Record<string, unknown>, key: string): string | null {
    let node: unknown = dict;
    for (const part of key.split('.')) {
      if (node && typeof node === 'object' && part in (node as Record<string, unknown>)) {
        node = (node as Record<string, unknown>)[part];
      } else {
        return null;
      }
    }
    return typeof node === 'string' ? node : null;
  }

  private restore(): Lang {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'en' ? 'en' : 'bg';
    } catch {
      return 'bg';
    }
  }
}

declare const ngDevMode: boolean | undefined;
