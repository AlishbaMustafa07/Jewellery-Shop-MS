# New Al-Noor Jewellers — Shop Management System

React + Django REST + PostgreSQL implementation of the *New Al-Noor Jewellers Technical Specification* (Sep 2026):
stock for gold/silver/palladium, daily gold rate, counter sales with receipts, customers & suppliers/karigar,
cash book with day close, old-gold exchange & refining, investors, zakat, reports/exports, users & audit trail,
and the one-time import of the 2024 workbook.

```
backend/    Django 5 + DRF API (apps: core, stock, parties, sales, cashbook, refining, investors, reports)
frontend/   React 19 + Vite + React Query single-page app
```

## Quick start (development)

Requirements: Python 3.11+, Node 20+, PostgreSQL 14+ (SQLite works for a quick trial).

```bash
# 1. Backend
cd backend
pip install -r requirements.txt
cp .env.example .env            # set DATABASE_URL (PostgreSQL) and a real DJANGO_SECRET_KEY
python manage.py migrate
python manage.py setup_shop --owner owner --password "choose-a-strong-one" --shop-name "New Al-Noor Jewellers"
python manage.py runserver      # http://127.0.0.1:8000

# 2. Frontend (second terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173  (proxies /api and /media to :8000)
```

Want sample data to click around? On a **throw-away** database run `python manage.py seed_demo`
(users `owner`, `manager`, `accountant`, `sales`; password `alnoor@2026`).

No PostgreSQL installed? `docker compose up -d` starts one (see `docker-compose.yml`), or set
`DATABASE_URL=sqlite:///db.sqlite3` for a trial.

## Running in the shop (production)

1. `cd frontend && npm run build` — Django automatically serves `frontend/dist`, so the shop needs only one process.
2. In `backend/.env`: `DJANGO_DEBUG=0`, a long random `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` = the PC's LAN IP/hostname,
   PostgreSQL `DATABASE_URL`.
3. Run with a WSGI server, e.g. `pip install waitress` then
   `waitress-serve --listen=0.0.0.0:8000 config.wsgi:application` (Windows) or gunicorn (Linux).
   Counter PCs, the owner's phone and tablets open `http://<shop-pc>:8000`.
4. **Daily backup** — schedule `python manage.py backup` (Windows Task Scheduler / cron). It writes a dated folder to
   `BACKUP_DIR` with `pg_dump` (if available), a JSON fixture and a full Excel export, and deletes folders older than
   `BACKUP_RETENTION_DAYS` (90). Copy the folder off-site (USB/cloud) as well.
5. The owner can download a full Excel export at any time from **Reports → Download all data**.

## Importing the 2024 workbook (spec §8)

```bash
python manage.py import_workbook "Stock 2024.xlsx" --report import-report.xlsx      # dry run: nothing saved
python manage.py import_workbook "Stock 2024.xlsx" --commit                          # import for real
```

Sheets are recognised by name (Stock File / Silver / Palladium / Day Book / Profit / Misc) and columns by their
header text. Every `#DIV/0!` / `#REF!` cell, bad date and skipped row is listed in the report, together with
reconciliation totals (items, gross weight, pasa, cost, sales, cash-book in/out, investments) to compare with the
workbook. Historical sales are imported as paid invoices (`OLD-000001…`) **without** cash-book entries, because the
Day Book import already contains that cash. Run the dry run, fix the workbook, repeat, then `--commit` and start the
two-week parallel run.

## Roles

| | Owner | Manager | Accountant | Salesperson |
|---|:-:|:-:|:-:|:-:|
| Sales, stock, customers, advances | ✓ | ✓ | ✓ | ✓ |
| See purchase cost & profit | ✓ | ✓ | – | – |
| Set gold rate, void invoices/payments | ✓ | ✓ | – | – |
| Cash book (private heads: home/zakat/investors) | ✓ | ✓ | ✓ | public heads only |
| Close day / reopen day | ✓ / ✓ | ✓ / – | ✓ / – | – |
| Reports (P&L, account summary) | ✓ | ✓ | stock/sales/expenses | – |
| Investors, zakat, users, settings, full export | ✓ | – | – | – |
| Audit log | ✓ | – | ✓ | – |

The API enforces all of this; the UI only hides what a role cannot use. Discount limits per invoice come from
**Settings** (per-role default) or per user.

## Business rules implemented (spec §5)

- Gold wt = Gross − Big stone − Palladium/diamond ± Extra/less gold
- Pasa = Gold wt × Ratti kaat / 96 (stored to 4 dp)
- Gold price = Pasa × Rate per tola / 11.664 (computed from full-precision pasa, so BIN0001 → Rs 10,058 as in the spec)
- Total cost = Gold price + extra costs; money rounded to the nearest rupee
- Sale line = gold value at the day's sell rate + making + stone; invoice net = subtotal − discount
- Profit = line total − purchase cost (minus invoice discount), owner/manager only
- Old gold credit = pasa × buy rate / 11.664 − deduction
- Past gold rates are never changed; each sale/purchase stores the rate it used. Only today's rate can be corrected.
- Customer and supplier balances are denormalised but **recomputed from their ledgers** inside each transaction.
- Day close locks that day's cash-book entries. Voiding something from a locked day posts a reversal dated today.
- Every create/update/void/login is written to an immutable audit log with old/new values.

## Assumptions & open questions (spec §11–12)

These are configurable or clearly isolated so the owner's answers are easy to apply:

- **Making charges** — per line, choose fixed Rs, Rs/gram, Rs/tola or % of gold value. When the owner confirms a
  rule it can become the default.
- **Sale gold basis** — Settings: pasa × rate (default) or gold weight × rate.
- **Investor profit** — the investor page shows both "share % of net profit" and "% of capital per month"; one click
  records either as a payment.
- **Zakat** — choose gold at sell/buy rate or cost, and whether to deduct supplier payables; rate % in Settings.
- **Account summary** (Refine / Profit retention / Shop purchase) is marked provisional.
- Home and zakat heads are *drawings* (below net profit). Supplier payments are stock purchases, not expenses.
- Walk-in sales must be paid in full. Leaving a balance requires a saved customer.
- Code prefixes per category live in Settings; codes are globally unique (`R0111`, `NS0027`…).
- Receipts, item tags (with Code 128 barcodes for scanners) and statements are printable HTML (A4 or 80 mm);
  "Print / PDF" uses the browser's *Save as PDF*.
- Not built yet (Phase 3 in the spec): WhatsApp receipts/reminders, offline mode, Urdu UI, OTP for the owner,
  FBR/GST integration.

## API

Base `/api/v1/`, JWT bearer auth (`/auth/login/`, `/auth/refresh/`, `/auth/logout/`, `/auth/me/`). All endpoints in
spec §6 are implemented, plus a few helpers (`/stock/calculate/`, `/stock/categories/`, `/stock/tags/`,
`/payments/{id}/void/`, `/old-gold/`, `/customers/{id}/payments/`, `/suppliers/{id}/payments/`,
`/cash-book/day-summary/`). Lists support `?page=&page_size=&search=&ordering=` and filters. Many list/report
endpoints accept `?format=xlsx|csv|html`. Errors are `{"detail": "...", "errors": {...}}`.

## Tests

```bash
cd backend && python manage.py test
```

Covers the spec formulas (including the BIN0001 example), code generation, the full sale → payment → void cycle,
advances and old gold, discount limits, walk-in rules, day close/reopen and locking, private-head visibility,
role restrictions, reports and exports, refining and investors.

Keyboard shortcuts: **Alt+N** new sale · **Alt+K** stock search · **Alt+D** day close.
