import { ChangeDetectionStrategy, Component, WritableSignal, inject, signal } from '@angular/core';

import { AuthService } from '../../core/auth.service';
import { IconComponent } from '../../ui/icon.component';

@Component({
  selector: 'app-auth',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IconComponent],
  templateUrl: './auth.component.html',
})
export class AuthComponent {
  private auth = inject(AuthService);

  mode = signal<'login' | 'register'>('login');
  email = signal('');
  password = signal('');
  tenant = signal('');
  error = signal('');
  busy = signal(false);

  set(sig: WritableSignal<string>, e: Event): void {
    sig.set((e.target as HTMLInputElement).value);
  }

  switch(mode: 'login' | 'register'): void {
    this.mode.set(mode);
    this.error.set('');
  }

  async submit(e: Event): Promise<void> {
    e.preventDefault();
    if (this.busy()) return;
    this.error.set('');
    this.busy.set(true);
    try {
      if (this.mode() === 'login') {
        await this.auth.login(this.email().trim(), this.password());
      } else {
        await this.auth.register(this.email().trim(), this.password(), this.tenant().trim());
      }
    } catch (err: any) {
      const detail = err?.error?.detail;
      this.error.set(detail || 'Something went wrong. Check your details and try again.');
    } finally {
      this.busy.set(false);
    }
  }
}
