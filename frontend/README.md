# Frontend - Ledgerly (Angular 19)

A conversational accounting workspace built on Angular 19 (standalone components +
signals). One codebase, two build targets:

1. **Standalone app** - a three-pane workspace (rail, conversation, inspector).
2. **Embeddable Web Component** - `<ledgerly-assistant>`, an Angular Element that drops
   into any host site and talks to the Ledgerly backend.

Design language ("Ledger Instrument"): warm ledger paper, pine-green ink, an ochre
accent, a serif display face (Fraunces), grotesk body (Hanken Grotesk) and tabular
mono figures (IBM Plex Mono). All design tokens live in `src/styles.scss`.

## Run

```bash
npm install
npm start                 # standalone app on http://localhost:4200
npm run build             # production build -> dist/frontend
npm run build:widget      # embeddable widget bundle -> dist/widget
```

The app calls the backend at `http://localhost:8000` by default (start it first; see
`../backend`). Override with `window.__LEDGERLY_API_BASE__` or the widget's `api-base`.

## Architecture

```
src/app/
  core/        models · api.service (+ ApiConfig) · assistant.service (intent router)
               workspace.store (signals: messages, working set, active invoice)
  ui/          icon · meter (confidence) · money pipe · format pipe
  features/
    chat/      conversation: composer, drag-drop ingest, empty state, starters
    cards/     rich result cards (invoice · validation · duplicates · documents · note)
    inspector/ active invoice summary + working set + quick actions
  widget/      compact assistant for embedding
  app.component  three-pane shell (standalone app)
main.ts          bootstraps the standalone app
main.widget.ts   registers <ledgerly-assistant> as a custom element
```

The `AssistantService` is a deterministic, client-side stand-in for the future
server-side LLM orchestrator: it routes intents (extract / validate / find
duplicates) to the real backend tools and renders grounded result cards. When the
LiteLLM gateway lands it becomes a single `/assistant/message` call; the message/card
contract is unchanged.

## Embedding the widget

After `npm run build:widget`, `dist/widget/` contains `main.js`, `polyfills.js` and
`styles.css` with stable (un-hashed) names. On any page:

```html
<link rel="stylesheet" href="/ledgerly/styles.css">
<script src="/ledgerly/polyfills.js" type="module"></script>
<script src="/ledgerly/main.js" type="module"></script>

<!-- size it with a wrapper; point it at your API -->
<div style="width:420px;height:560px">
  <ledgerly-assistant api-base="https://api.yourdomain.eu"></ledgerly-assistant>
</div>
```

`dist/widget/index.html` is a live demo of exactly this. The Fraunces / Hanken Grotesk
/ IBM Plex Mono fonts are loaded from Google Fonts in the demo host; a production embed
should self-host them.

> Note: this is an MVP UI over the stateless tools API. Auth, multi-tenant scoping and
> conversation persistence arrive with later backend phases.
