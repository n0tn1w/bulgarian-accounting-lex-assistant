---
marp: true
paginate: true
footer: "Счетоводен и правен асистент на български"
style: |
  @import url('https://fonts.googleapis.com/css2?family=PT+Serif:ital,wght@0,400;0,700;1,400;1,700&family=PT+Sans:ital,wght@0,400;0,700;1,400&display=swap');

  :root {
    --green: #2E4A3B;
    --green-dark: #253C30;
    --cream: #F4F1E7;
    --gold: #C2883C;
    --sage: #DDE6DC;
    --ink: #2A2A28;
    --muted: #8A8A82;
    --serif: 'PT Serif', Georgia, 'Times New Roman', serif;
    --sans: 'PT Sans', 'Helvetica Neue', Arial, sans-serif;
  }

  section {
    font-family: var(--sans);
    background: var(--cream);
    color: var(--ink);
    font-size: 24px;
    padding: 60px 70px 70px;
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
  }
  section.dark { justify-content: center; }

  /* eyebrow + title with gold vertical bar */
  .eyebrow {
    text-transform: uppercase;
    letter-spacing: .14em;
    font-size: 15px;
    color: var(--gold);
    font-weight: 700;
    margin: 0 0 2px 18px;
  }
  section > h2 {
    font-family: var(--serif);
    color: var(--green);
    font-size: 46px;
    font-weight: 700;
    margin: 0 0 28px 18px;
    line-height: 1.1;
  }
  /* gold bar beside the heading block */
  section.content::before {
    content: "";
    position: absolute;
    left: 70px; top: 60px;
    width: 6px; height: 86px;
    background: var(--gold);
    border-radius: 3px;
  }

  section ul { margin-top: 6px; }
  section li { margin: 0 0 14px 0; line-height: 1.4; }
  section li strong { color: var(--green); }

  /* sage callout */
  .callout {
    margin-top: 34px;
    background: var(--sage);
    border-radius: 14px;
    padding: 22px 30px;
    text-align: center;
    font-family: var(--serif);
    font-weight: 700;
    color: var(--green);
    font-size: 24px;
  }
  .lead-italic {
    font-family: var(--serif);
    font-style: italic;
    color: var(--green);
    font-size: 20px;
    margin-top: 26px;
  }

  /* footer + pagination */
  section footer { color: var(--muted); font-size: 13px; font-family: var(--sans); }
  section::after { color: var(--muted); font-size: 14px; }

  /* ---------- DARK slides (title / closing) ---------- */
  section.dark {
    background: var(--green);
    color: #EDEFEA;
    border-top: 10px solid var(--gold);
    border-bottom: 10px solid var(--gold);
  }
  section.dark .eyebrow { color: var(--gold); margin-left: 0; }
  section.dark h1 {
    font-family: var(--serif);
    color: #F3F4EF;
    font-size: 60px;
    line-height: 1.08;
    margin: 8px 0 16px;
  }
  section.dark .sub { color: #C9D2C8; font-size: 24px; }
  section.dark .accent { color: var(--gold); font-weight: 700; }
  section.dark .names {
    margin-top: 40px; color: #BFC9BD; font-size: 18px;
  }
  section.dark .card-names {
    margin-top: 46px; background: rgba(255,255,255,.05);
    border-radius: 16px; padding: 22px 28px; font-size: 18px; line-height: 1.7;
  }
  section.dark .card-names b { color: #F3F4EF; }
  section.dark .card-names span { color: #AEB8AC; }

  /* DEMO interstitial slide */
  section.demo { text-align: center; align-items: center; }
  section.demo h1 { font-size: 124px; letter-spacing: .08em; margin: 0 0 10px; }
  section.demo .sub { text-align: center; color: #C9D2C8; }

  /* ---------- Architecture diagram ---------- */
  .arch { display: flex; align-items: center; gap: 14px; margin-top: 10px; }
  .arch .col { display: flex; flex-direction: column; gap: 18px; }
  .box {
    border-radius: 12px; padding: 14px 18px; text-align: center;
    border: 1.5px solid #D8D2BF; background: #FBFAF4;
  }
  .box b { font-family: var(--serif); color: var(--green); font-size: 21px; display: block; }
  .box small { color: #555; font-size: 14px; display: block; margin-top: 4px; }
  .box.sage { background: #E7EEE6; border-color: #C6D4C3; }
  .box.gold { background: #F6ECD9; border-color: #E3CDA0; }
  .box.gold b { color: var(--gold); }
  .box.dark { background: var(--green); border-color: var(--green); }
  .box.dark b { color: #F3F4EF; }
  .box.dark small { color: #C2CCC0; }
  .box.mid { min-width: 190px; }
  .box.full { width: 100%; margin-top: 6px; padding: 18px; }
  .arrow { color: var(--gold); font-size: 30px; font-weight: 700; }
  .arch-down { text-align: center; color: var(--gold); font-size: 30px; font-weight: 700; margin: 2px 0; }

  /* big emphasized preprocessing panel */
  .bigbox {
    border: 2.5px solid var(--gold);
    background: rgba(194,136,60,.07);
    border-radius: 18px;
    padding: 14px 24px 20px;
    margin-top: 2px;
  }
  .bigbox .biglabel {
    text-transform: uppercase; letter-spacing: .12em;
    font-size: 14px; font-weight: 700; color: var(--gold);
    margin-bottom: 10px;
  }
  .userflow { margin-top: 14px; }

  /* simplified preprocessing: inputs -> RAG stores (details on next slides) */
  .prep { display: flex; justify-content: center; gap: 80px; margin-top: 8px; }
  .prepcol { display: flex; flex-direction: column; align-items: center; gap: 6px; }
  .prepcol .box { width: 250px; }
  .down { color: var(--gold); font-size: 24px; font-weight: 700; line-height: 1; }

  /* LLM selects which RAG to use */
  .select-note { text-align: center; margin: 14px 0 6px; font-size: 16px; color: var(--ink); }
  .select-note .ud { color: var(--gold); font-weight: 700; font-size: 24px; margin-right: 8px; vertical-align: middle; }
  .select-note b { color: var(--green); }

  /* detailed RAG pipelines */
  .phase {
    text-transform: uppercase; letter-spacing: .12em;
    font-size: 13px; font-weight: 700; color: var(--gold);
    margin: 10px 0 2px 2px;
  }
  .arch.tight { gap: 10px; margin-top: 4px; }
  .arch.tight .col { gap: 12px; }
  .box.sm { padding: 10px 14px; }
  .box.sm b { font-size: 18px; }
  .box.sm small { font-size: 12.5px; margin-top: 2px; }

  /* ---------- Workflow steps ---------- */
  .steps { display: flex; flex-direction: column; gap: 16px; margin-top: 10px; }
  .step { display: flex; align-items: center; gap: 18px; }
  .num {
    flex: 0 0 auto; width: 42px; height: 42px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-family: var(--serif); font-weight: 700; color: #fff; font-size: 20px;
  }
  .num.dark { background: var(--green); }
  .num.gold { background: var(--gold); }
  .step b { font-family: var(--serif); color: var(--green); font-size: 22px; display: block; }
  .step small { color: #555; font-size: 16px; display: block; }

  /* ---------- evaluation results ---------- */
  .evalgrid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-top: 10px; }
  .evalcard { border: 1.5px solid #D8D2BF; background: #FBFAF4; border-radius: 14px; padding: 16px 24px 18px; }
  .evalcard.r1 { border-top: 5px solid var(--green); }
  .evalcard.r2 { border-top: 5px solid var(--gold); }
  .evalcard h3 { font-family: var(--serif); color: var(--green); font-size: 23px; margin: 2px 0 0; }
  .evalcard .sub2 { color: #888; font-size: 13px; margin: 0 0 8px; }
  .mrow { display: flex; justify-content: space-between; align-items: baseline; padding: 6px 0; border-bottom: 1px dashed #E2DCCB; font-size: 16px; }
  .mrow:last-child { border-bottom: none; }
  .mrow .lbl { color: var(--ink); }
  .mrow .val { font-family: var(--serif); font-weight: 700; color: var(--green); white-space: nowrap; }
  .mrow .val.gold { color: var(--gold); }
  .evaltotal { margin-top: 10px; text-align: right; font-family: var(--serif); font-weight: 700; color: var(--green); font-size: 19px; }
  .evalcard.r2 .evaltotal { color: var(--gold); }

  /* ---------- 2-col cards (value) ---------- */
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px 22px; margin-top: 10px; }
  .card {
    border: 1.5px solid #D8D2BF; background: #FBFAF4; border-radius: 14px;
    padding: 16px 22px; text-align: center;
  }
  .card b { font-family: var(--serif); color: var(--green); font-size: 21px; display: block; }
  .card p { color: #555; font-size: 15px; margin: 6px 0 0; line-height: 1.4; }
---

<!-- _class: dark -->
<!-- _paginate: false -->
<!-- _footer: "" -->

<div class="eyebrow">Проект · Изкуствен интелект</div>

# Счетоводен и правен асистент на български

<div class="sub">AI асистент за счетоводители — два RAG агента (фактури и законодателство) + LLM</div>

<div class="card-names">
<b>Мая Денева</b> <span>· ИИ</span><br>
<b>Благовест Папазов</b> <span>· ИИ</span><br>
<b>Даниел Манчевски</b> <span>· ИИ</span>
</div>

---

<!-- _class: content -->

<div class="eyebrow">Контекст</div>

## Проблемът пред счетоводителите

- **Голям обем документи** във всякакви формати — фактури, дневници, PDF/сканове, XML и CSV експорти от различни програми.
- **Сложно и променящо се законодателство** — ЗДДС, ЗКПО, ЗСч, ДОПК; трудно е бързо да се намери точният член.
- **Ръчната обработка е бавна и крие грешки** — грешни суми, пропуснат ДДС, дубликати.
- **Общите AI инструменти не са надеждни** — не познават данните на клиента, „измислят" числа и не цитират източник.

<div class="callout">Нужен е асистент, който разбира българските документи и закони — и отговаря обосновано.</div>

---

<!-- _class: content -->

<div class="eyebrow">Идеята</div>

## Какво представлява асистентът

- **AI асистент на български** в областта на счетоводството и правото.
- **Два RAG агента:** (1) индексира и извлича от фактури и счетоводни документи; (2) търси в база с българско законодателство.
- **Контекст → LLM:** извлечените данни се подават на езиков модел (Claude / локален), който генерира точни отговори с цитати.
- **Достъпен интерфейс** — подходящ за хора с малка или без техническа подготовка.

<div class="callout">„ChatGPT за счетоводители" — но обоснован в реалните документи и в закона.</div>

---

<!-- _class: content -->

<div class="eyebrow">Архитектура</div>

## Два RAG агента и LLM

<div class="bigbox">
  <div class="biglabel">Предварителна обработка · еднократно индексиране (офлайн)</div>
  <div class="prep">
    <div class="prepcol">
      <div class="box sm"><b>Документи</b><small>фактури · PDF · XML/CSV</small></div>
      <div class="down">↓</div>
      <div class="box sm sage"><b>RAG 1 — Фактури</b><small>готов индекс на фактурите</small></div>
    </div>
    <div class="prepcol">
      <div class="box sm"><b>Закони</b><small>ЗДДС · ЗКПО · ЗСч · ДОПК</small></div>
      <div class="down">↓</div>
      <div class="box sm gold"><b>RAG 2 — Закони</b><small>готов индекс на законите</small></div>
    </div>
  </div>
</div>

<div class="select-note"><span class="ud">⇅</span> LLM избира <b>кой RAG</b> да използва според въпроса — RAG 1, RAG 2 или двата</div>

<div class="phase userflow">Заявка от потребителя (онлайн)</div>
<div class="arch tight" style="justify-content:center;">
  <div class="box sm dark"><b>Потребител</b><small>въпрос на български</small></div>
  <div class="arrow">→</div>
  <div class="box sm mid"><b>LLM — чат-оркестратор</b><small>избира и извиква RAG-а</small></div>
  <div class="arrow">→</div>
  <div class="box sm dark"><b>Отговор с цитати</b><small>към фактури и членове от закона</small></div>
</div>

<div class="lead-italic">Числата идват от данните и закона — не са измислени; всеки отговор сочи към източник.</div>

---

<!-- _class: content -->

<div class="eyebrow">Обработка на фактури</div>

## От качване до запис в базата

<div class="phase">Разчитане на документа</div>
<div class="arch tight">
  <div class="col">
    <div class="box sm"><b>XML / CSV</b><small>парсване (Controlisy/UBL)</small></div>
    <div class="box sm"><b>PDF</b><small>OCR (Tesseract)</small></div>
    <div class="box sm"><b>Снимки (JPG/PNG)</b><small>OCR + Vision при ниска увереност</small></div>
  </div>
  <div class="arrow">→</div>
  <div class="box sm sage"><b>Извличане на полета + класификация</b><small>№ · дата · контрагенти · ЕИК · ДДС · суми · редове</small></div>
</div>

<div class="arch-down">↓</div>

<div class="phase">Валидиране и запис</div>
<div class="arch tight">
  <div class="box sm"><b>Справка по ЕИК</b><small>търговски регистър</small></div>
  <div class="arrow">→</div>
  <div class="box sm"><b>Валидация + дедупликация</b><small>нето+ДДС=общо · ставки · ЕИК · дубликати</small></div>
  <div class="arrow">→</div>
  <div class="box sm"><b>Ембединг</b><small>BGE-M3 + BM25</small></div>
  <div class="arrow">→</div>
  <div class="box sm dark"><b>Запис · Postgres + pgvector</b><small>multi-tenant · RLS</small></div>
</div>

<div class="lead-italic">Резултатът захранва RAG 1 — Фактури; всяко поле носи оценка за увереност.</div>

---

<!-- _class: content -->

<div class="eyebrow">Архитектура · RAG 1</div>

## RAG за фактури

<div class="phase">Индексиране (офлайн)</div>
<div class="arch tight">
  <div class="box sm"><b>stored_invoices</b><small>Postgres + pgvector · RLS</small></div>
  <div class="arrow">→</div>
  <div class="box sm"><b>invoice_to_text</b><small>каноничен текст за индекса</small></div>
  <div class="arrow">→</div>
  <div class="col">
    <div class="box sm sage"><b>BGE-M3 → pgvector</b><small>плътен вектор · HNSW (1024)</small></div>
    <div class="box sm gold"><b>BM25</b><small>разреден · per tenant</small></div>
  </div>
</div>

<div class="arch-down">↓</div>

<div class="phase">Заявки (онлайн)</div>
<div class="arch tight">
  <div class="box sm"><b>Въпрос + дати</b><small>детерминирано парсване</small></div>
  <div class="arrow">→</div>
  <div class="col">
    <div class="box sm"><b>Структурни SQL инструменти</b><small>get · filter · sum · compare</small></div>
    <div class="box sm sage"><b>Семантично търсене</b><small>dense + BM25 → RRF</small></div>
  </div>
  <div class="arrow">→</div>
  <div class="box sm dark"><b>Резултати + цитати</b><small>към всяка фактура</small></div>
</div>

---

<!-- _class: content -->

<div class="eyebrow">Архитектура · RAG 2</div>

## RAG за законодателство

<div class="phase">Индексиране (офлайн)</div>
<div class="arch tight">
  <div class="box sm"><b>lex.bg → НАП</b><small>скрейпинг + кеш</small></div>
  <div class="arrow">→</div>
  <div class="box sm"><b>Чънкване</b><small>Чл. / ал. / т.</small></div>
  <div class="arrow">→</div>
  <div class="col">
    <div class="box sm sage"><b>BGE-M3 → ChromaDB</b><small>плътен вектор · HNSW</small></div>
    <div class="box sm gold"><b>BM25</b><small>разреден · BG токенизатор</small></div>
  </div>
</div>

<div class="arch-down">↓</div>

<div class="phase">Извличане (онлайн)</div>
<div class="arch tight">
  <div class="box sm"><b>Въпрос</b><small>на български</small></div>
  <div class="arrow">→</div>
  <div class="box sm sage"><b>Хибридно търсене</b><small>dense + BM25 → RRF</small></div>
  <div class="arrow">→</div>
  <div class="box sm"><b>Cross-encoder</b><small>BGE-reranker v2-m3</small></div>
  <div class="arrow">→</div>
  <div class="box sm dark"><b>Топ-5 + цитати</b><small>Чл./ал./т. · отказ при липса</small></div>
</div>

<div class="lead-italic">Под праг на увереност системата отказва, вместо да отговори без източник.</div>

---

<!-- _class: content -->

<div class="eyebrow">Оценка</div>

## Резултати от оценката

<div class="evalgrid">
  <div class="evalcard r1">
    <h3>RAG 1 — Фактури</h3>
    <div class="sub2">детерминирани инструменти · 46 случая · без LLM</div>
    <div class="mrow"><span class="lbl">Търсене по номер</span><span class="val">100%</span></div>
    <div class="mrow"><span class="lbl">Филтри (recall + брой)</span><span class="val">100%</span></div>
    <div class="mrow"><span class="lbl">Агрегации (±0.01 лв.)</span><span class="val">100%</span></div>
    <div class="mrow"><span class="lbl">Семантично (recall@10 / MRR)</span><span class="val">100% / 1.0</span></div>
    <div class="mrow"><span class="lbl">Тренд / сравнение</span><span class="val">100%</span></div>
    <div class="evaltotal">Общо · 46/46 = 100%</div>
  </div>
  <div class="evalcard r2">
    <h3>RAG 2 — Закони</h3>
    <div class="sub2">извличане · P / R / MRR@8 · 16 случая</div>
    <div class="mrow"><span class="lbl">Намерен верен член (recall@8)</span><span class="val gold">—</span></div>
    <div class="mrow"><span class="lbl">Среден MRR</span><span class="val gold">—</span></div>
    <div class="mrow"><span class="lbl">Точност@8 (precision)</span><span class="val gold">—</span></div>
    <div class="mrow"><span class="lbl">Покритие (ЗДДС · ЗКПО · ЗДДФЛ · КСО)</span><span class="val gold">—</span></div>
    <div class="evaltotal">Общо · —/16</div>
  </div>
</div>

<div class="lead-italic">Синтетичен, възпроизводим набор; всяка стойност се смята детерминирано. Phase 2 (агент): маршрутизиране · отказ · цитиране на член — отделна оценка.</div>

---

<!-- _class: content -->

<div class="eyebrow">Възможности</div>

## Какво може да прави асистентът днес

<div class="grid2">
  <div class="card"><b>Качване на документи</b><p>XML/Controlisy, PDF, сканове и снимки; автоматично разчитане дори на размазани изображения.</p></div>
  <div class="card"><b>Преглед и редакция</b><p>извлечени № / дата / контрагенти / ЕИК / ДДС № / суми; несигурните полета са маркирани; справка по ЕИК.</p></div>
  <div class="card"><b>Проверка за грешки</b><p>валидация (нето + ДДС = общо, ставка, ЕИК/ДДС №, пълнота) и откриване на дубликати.</p></div>
  <div class="card"><b>Въпроси за моите фактури (BG/EN)</b><p>търсене, филтри, суми по доставчик/месец/ставка, сравнение на периоди, търсене по тема — с цитати.</p></div>
  <div class="card"><b>Въпроси за закона</b><p>ЗДДС, ЗКПО, ЗДДФЛ, КСО, ДОПК… с цитат до член (Чл./ал./т.) и източник; отказ при липса на източник.</p></div>
  <div class="card"><b>Чат асистент</b><p>разговор на BG/EN, качване на файлове в чата, история и запазена работна селекция.</p></div>
</div>

---

<!-- _class: content -->

<div class="eyebrow">Защо е различен</div>

## Предимства на решението

- **Български** — език и законодателство (ЗДДС, ЗКПО, ЗСч).
- **Обосновани и проверими отговори** — всеки отговор цитира източник (фактура или член от закона); ако такъв не е наличен, не посочва отговор.
- **Детерминирани изчисления** — числата се смятат от инструменти, а не от модела.
- **За нетехнически потребители** — чист, разбираем интерфейс.
- **Гъвкав модел** — локален (Ollama) за поверителност или облачен (Claude/GPT) за качество.
- **Съобразен с EU/BG изисквания** — GDPR и готовност за ViDA/SAF-T.

---

<!-- _class: dark demo -->
<!-- _footer: "" -->
<!-- _paginate: false -->

# ДЕМО

<div class="sub">на живо</div>

---

<!-- _class: dark -->
<!-- _footer: "" -->
<!-- _paginate: false -->

# Точни счетоводни и правни отговори — на български, обосновани и достъпни.

<div class="accent" style="font-size:24px; margin-bottom:8px;">Благодарим за вниманието!</div>

<div class="names">Мая Денева · Благовест Папазов · Даниел Манчевски</div>
