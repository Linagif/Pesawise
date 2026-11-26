# PesaWise: Student Budget Manager

![Tests](https://github.com/YOUR-USERNAME/PesaWise/actions/workflows/tests.yml/badge.svg)

A budgeting and financial-health web app for Kenyan university students, built with **Django**. Students record money from
parents and casual jobs, plan monthly budgets, log daily spending, track savings goals, import M-Pesa messages, and get
**evidence-based** guidance: every number is calculated from their own records, and the advisor says nothing when there is not
enough data to be honest.

**Live demo:** _add your link here_ (press **Try the demo**: no sign-up, private sample account, deleted after 24 hours).

> PesaWise is a budgeting aid, not professional financial advice. It never asks for an M-Pesa PIN, OTP or bank password.

## Screenshots

_Add images to `docs/screenshots/` and link them here._
Suggested shots: dashboard · daily expenses · budget with progress bars · Financial Health · What-if simulator ·
Recommendations · M-Pesa review screen · a downloaded PDF report. (Use the demo account: all data is fake.)

## What it does

| Area | Highlights |
|---|---|
| **Everyday tracking** | Income (regular or irregular), monthly budgets, a one-tap **quick-add expense** on every page, savings goals with contribution history |
| **Dashboard & reports** | Summary cards, five Chart.js charts, seven report types, **CSV and PDF export** |
| **Financial Health** | Net cash flow, savings rate, essential vs discretionary split, emergency-fund coverage, month-on-month category changes, small purchases that add up, recurring-payment detection |
| **What-if simulator** | "Can I afford KSh 60,000?", "Can I save KSh 10,000 a month?", "What if I cut food by KSh 1,500?", "What if my income drops 20%?": answered from the student's own history, with assumptions and limitations shown |
| **Recommendations** | Stored, evidence-backed suggestions with confidence, priority, review date, accept/dismiss/complete, feedback, and honest outcome tracking |
| **M-Pesa SMS import** | Paste confirmation messages, review them, then save. Handles sent, received, till, paybill, withdraw, deposit, airtime and reversals, with fees recorded separately and duplicates blocked |
| **Dark mode** | Choose **Light**, **Dark** or **Device default** from a menu in the top bar (or the Appearance card on the Profile page). Remembered on the device, no flash on load, charts redraw to match, and every colour pair is tested for WCAG AA contrast |
| **Installable app (PWA)** | Installs on a phone from the browser, with its own icon and full-screen launch. It never stores your records on the device |
| **Demo mode** | A private, disposable sample account for every visitor |

## Design decisions

These are the choices I would want to talk about in an interview.

1. **Money is `Decimal`, never float.** Totals are rounded half-up to 2 places, and a test proves `0.10 + 0.20 = 0.30`.
2. **Totals are computed, not stored.** Budget totals, savings progress and balances are recalculated from the records, so editing or deleting
   a transaction can never leave a stale number. Savings exist only as contributions, so they are subtracted exactly once.
3. **Calculations live in service modules**, not in views or templates, so they are independently testable.
4. **No data, no advice.** Every insight has a minimum-data rule (for example two full months before comparing categories). A partial
   month is never compared with a full one.
5. **Recommendations are safe by construction.** Savings suggestions only come out of *free cash* (never more than half of it), essential
   categories are never told to "cut", and a dismissed suggestion is not repeated for 30 days.
6. **Outcome tracking never claims causation.** It shows what happened to spending after a recommendation was accepted, and says that other
   things may have changed.
7. **The importer is evidence-only.** It pre-selects a category only when the message says what it was, or the student already confirmed that
   recipient. An unknown "JOHN KAMAU" is never guessed to be groceries or rent. Nothing is saved until the student confirms.
8. **Idempotent import.** The M-Pesa transaction code is unique per student, so re-pasting never double-counts.
9. **Data minimisation.** The importer keeps amount, fee, name, date and code, and drops phone numbers, account numbers, balances and the
   original message text.
10. **Rule-based first.** No machine learning or external AI services. With a few weeks of data per student, transparent rules beat a model
    that cannot be properly evaluated.

## Security and privacy

- Django password hashing, CSRF on every form, login required on every private page, secure cookies when `DEBUG=False`.
- **Strict per-student isolation:** every query is filtered by the logged-in user, and other students' records return 404. Tests check this
  for every module.
- Validated inputs (positive amounts, no future dates, category ownership), POST-only deletes with confirmation, duplicate-submission protection.
- CSV export neutralises spreadsheet-formula injection; PDF export escapes user text.
- Demo accounts have **no usable password**, expire after 24 hours, are capped in number, and the feature is **off unless explicitly enabled**.
- Secrets come from environment variables. Real statements and messages must never be committed (see `.gitignore`).

## Testing

```bash
python manage.py test        # 280 tests
```

Covers authentication, access control, end-to-end browser-script tests (real pages and real clicks in jsdom; run `npm install --no-save jsdom` to enable them locally), the service worker's privacy rules and the theme script (run in Node against mock browser APIs), colour contrast, every calculation (including zero and edge cases), data isolation, the parser (with invented
messages), the recommendation lifecycle, exports and demo mode. GitHub Actions runs the suite, `manage.py check` and a missing-migration
check on every push.

## Run it locally

```bash
python -m venv venv
venv\Scripts\activate                 # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo            # optional: local student  demo / demo12345  with fake data
python manage.py runserver            # http://127.0.0.1:8000
```

Settings come from environment variables or a `.env` file (see `.env.example`).

### Demo mode

| Setting | Effect |
|---|---|
| `DJANGO_DEMO_ENABLED=True` | Shows **Try the demo** on the login page. Enabled automatically when `DEBUG=True`. |
| `python manage.py purge_demo` | Deletes demo accounts older than 24 hours. Run it hourly from a scheduled job in production. |

## Install on a phone

PesaWise is a Progressive Web App: open the live site on a phone and use **Install app** (Android Chrome) or **Share, then Add to Home Screen**
(iPhone Safari). The service worker caches only static files and an offline page, never personal data. Details and tests: `docs/PWA.md`.

## Deploy (HTTPS)

`render.yaml` and `docs/DEPLOYMENT.md` set up a free Render deployment with PostgreSQL, gunicorn, WhiteNoise static files and
HTTPS. In production the app refuses to start without a secret key, redirects HTTP to HTTPS, and uses secure cookies. CI runs the test
suite on both SQLite and PostgreSQL.

## Project structure

```
core/        categories, shared utilities, demo data          income/    income records
accounts/    registration, profile, demo sandbox              budgets/   monthly budgets and limits
expenses/    daily expense tracking                            savings/   goals and contributions
dashboard/   calculation services, dashboard, reports, exports
advisor/     analysis.py (health), simulator.py, recommendations.py, rules.py (alerts)
imports/     parser.py (M-Pesa SMS), services.py (review workflow)
docs/        SRS, user guide, test results
```

## Not built yet (deliberately)

Bank statement parsing and aggregator APIs, machine-learning forecasts and categorisation, an LLM coach, field-level encryption and a
"delete all my data" button. These are the right next steps if the app is opened to real users.
