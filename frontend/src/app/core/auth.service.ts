import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { ApiService } from './api.service';
import { AuthUser, TokenResponse } from './models';

const TOKEN_KEY = 'ledgerly_token';

/** Holds the JWT + current user. Token is read by the HTTP interceptor. */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private api = inject(ApiService);

  readonly token = signal<string | null>(localStorage.getItem(TOKEN_KEY));
  readonly user = signal<AuthUser | null>(null);
  readonly isAuthed = computed(() => !!this.user());
  readonly ready = signal(false); // true once we've tried to restore a session

  private setSession(res: TokenResponse): void {
    localStorage.setItem(TOKEN_KEY, res.access_token);
    this.token.set(res.access_token);
    this.user.set(res.user);
  }

  async login(email: string, password: string): Promise<void> {
    this.setSession(await firstValueFrom(this.api.login(email, password)));
  }

  async register(email: string, password: string, tenantName: string): Promise<void> {
    this.setSession(await firstValueFrom(this.api.register(email, password, tenantName)));
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    this.token.set(null);
    this.user.set(null);
  }

  /** Validate a stored token on app start (call once, after DI is built). */
  async restore(): Promise<void> {
    if (!this.token()) {
      this.ready.set(true);
      return;
    }
    try {
      this.user.set(await firstValueFrom(this.api.me()));
    } catch {
      this.logout();
    } finally {
      this.ready.set(true);
    }
  }
}
