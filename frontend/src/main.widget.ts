// Entry point for the embeddable web component build (npm run build:widget).
// Registers <ledgerly-assistant> as a custom element.
import { createApplication } from '@angular/platform-browser';
import { createCustomElement } from '@angular/elements';
import { provideHttpClient, withFetch } from '@angular/common/http';
import { provideZoneChangeDetection } from '@angular/core';

import { WidgetComponent } from './app/widget/widget.component';

(async () => {
  const app = await createApplication({
    providers: [
      provideZoneChangeDetection({ eventCoalescing: true }),
      provideHttpClient(withFetch()),
    ],
  });

  const element = createCustomElement(WidgetComponent, { injector: app.injector });
  if (!customElements.get('ledgerly-assistant')) {
    customElements.define('ledgerly-assistant', element);
  }
})();
