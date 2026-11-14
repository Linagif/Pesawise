# PesaWise – Student Budget Manager

A web-based personal finance system for university students (Python 3 + Django, SQLite, Bootstrap 5, Chart.js).
Record money received from parents and casual jobs, plan a monthly budget, log every daily purchase, track savings goals,
see charts and reports, and get simple rule-based money tips. Currency: Kenyan Shilling (KSh).

> Web application only (no Android/iOS/PWA). No external APIs or AI services. PesaWise never asks for M-Pesa PINs or bank passwords.

## 1. Quick start (Windows / macOS / Linux, VS Code terminal)

```bash
# 1. open the PesaWise folder in VS Code, then open a terminal
python -m venv venv

# 2. activate the virtual environment
venv\Scripts\activate            # Windows (PowerShell: venv\Scripts\Activate.ps1)
source venv/bin/activate         # macOS / Linux

# 3. install Django
pip install -r requirements.txt

# 4. (optional) create your settings file
copy .env.example .env           # Windows   |   cp .env.example .env   (macOS/Linux)

# 5. create the database tables (also loads the default categories)
python manage.py migrate

# 6. (optional) create the demo student "demo" / "demo12345" with sample data
python manage.py seed_demo

# 7. run the server, then open http://127.0.0.1:8000
python manage.py runserver
```

Create an admin account for the Django admin site (`/admin/`) with `python manage.py createsuperuser`.
Bootstrap, Chart.js and the font load from a CDN, so the browser needs an internet connection.

## 2. Run the tests

```bash
python manage.py test            # 72 tests; see docs/TEST_RESULTS.md
```

## 3. Project structure and purpose of each important file

| Path | Purpose |
|---|---|
| `config/settings.py` | Settings. Secrets come from environment variables / `.env`. Time zone Africa/Nairobi. |
| `config/urls.py` | Top-level URL routing (login/logout/password reset use Django's built-in auth views). |
| `core/models.py` | `Category` – default + custom expense categories, income sources and the "Savings" budget line. |
| `core/migrations/0002_default_categories.py` | Loads the default categories into every new database. |
| `core/utils.py`, `core/validators.py` | Decimal rounding (`money`), week/month ranges, shared validators (positive amount, not in future). |
| `core/forms.py`, `core/templatetags/money.py` | Bootstrap form styling; the `kes` filter formats `KSh 1,234.50`. |
| `core/context_processors.py` | Puts the quick-add expense form on every page (modal in `base.html`). |
| `accounts/` | Registration, profile (with optional daily spending target), `Profile` model, styled auth forms. |
| `income/` | `Income` model; add/edit/delete/list with filters and source comparison. |
| `budgets/` | `Budget` + `BudgetAllocation`; monthly budgets, category limits, copy-last-month. |
| `expenses/` | `Expense` model; **daily expense tracking**: quick add, daily view, list with search and filters. |
| `savings/` | `SavingsGoal` + `SavingsContribution`; progress is calculated, never stored. |
| `dashboard/services.py` | **All financial calculations** (balance, budget utilization, totals, series). Uses `Decimal`. |
| `dashboard/views.py` | Dashboard (cards, charts data, recent transactions) and the 7 report types. |
| `dashboard/management/commands/seed_demo.py` | Creates demo data for demonstrations. |
| `advisor/rules.py` | The rule-based advisor (budget, daily average, unplanned spending, savings, negative balance). |
| `templates/` | `base.html` (layout, sidebar, quick-add modal), `form_page.html`/`confirm_delete.html` (generic), one folder per app. |
| `static/css/style.css`, `static/js/app.js` | Look and feel; double-submit protection. |
| `*/tests.py`, `core/testing.py` | Automated tests and shared test helpers. |
| `docs/` | SRS (with use-case diagram and ERD), user guide, test results. |

## 4. How the money maths works (summary)

```
Available balance = Total income − Total expenses − Savings contributions
Remaining category budget = Allocated − Actual spending in that category
Utilization % = Actual ÷ Allocated × 100        (zero budget handled safely)
Savings progress % = (Starting amount + contributions) ÷ Target × 100
```
Savings are stored only as contributions (never as expenses), so they are subtracted exactly once.
Totals and balances are always recomputed from the records, so edits and deletes can never leave them wrong.
Full rules: `docs/SRS.md`, section 8.

## 5. Security summary
Password hashing (Django PBKDF2), CSRF on every form, login required everywhere, every query filtered by the logged-in user,
object lookups return 404 for other students' records, POST-only deletes with confirmation, validated Decimal inputs,
duplicate-submission protection, secrets in environment variables, secure cookies when `DJANGO_DEBUG=False`.
Run `DJANGO_DEBUG=False python manage.py check --deploy` before deploying.

## 6. Design decisions
- `Category` lives in a small shared `core` app (used by income, expenses and budgets).
- Budget totals and savings "current amount" are calculated from their parts, not stored.
- A "Savings" budget line counts that month's contributions; spending in categories without a limit still counts against the monthly total.
- Weeks run Monday to Sunday. Deletes are permanent (after confirmation).
