# PesaWise – Test Results

Run with `python manage.py test -v 2`.

**Result: 72 of 72 tests passed.**

| Area | Tests | Passed |
|---|---:|---:|
| accounts.tests.AccessControlTests | 2 | 2 |
| accounts.tests.ProfileTests | 2 | 2 |
| accounts.tests.RegistrationLoginTests | 5 | 5 |
| advisor.tests.AdvisorTests | 8 | 8 |
| budgets.tests.BudgetTests | 11 | 11 |
| dashboard.tests.CalculationTests | 7 | 7 |
| dashboard.tests.DashboardViewTests | 6 | 6 |
| expenses.tests.ExpenseTests | 13 | 13 |
| income.tests.IncomeTests | 9 | 9 |
| savings.tests.SavingsTests | 9 | 9 |

## Detail

### accounts.tests.AccessControlTests
- PASS: every private page requires login
- PASS: logout requires post

### accounts.tests.ProfileTests
- PASS: cannot take another users email
- PASS: update profile and daily target

### accounts.tests.RegistrationLoginTests
- PASS: bad login rejected
- PASS: login and logout
- PASS: password reset page and email
- PASS: register creates user profile and logs in
- PASS: register rejects duplicate email and weak password

### advisor.tests.AdvisorTests
- PASS: above average tip with enough history
- PASS: no average tip without enough history
- PASS: no data gives getting started only
- PASS: overspend and near limit rules
- PASS: prompts for budget when none
- PASS: savings progress tip
- PASS: tips only from own data and page renders
- PASS: unplanned purchases rule

### budgets.tests.BudgetTests
- PASS: add edit delete allocation
- PASS: allocations total example from spec
- PASS: copy previous budget
- PASS: create budget and prevent duplicate month
- PASS: isolation
- PASS: remaining and utilization example from spec
- PASS: same category cannot be allocated twice or negative
- PASS: savings line uses contributions not expenses
- PASS: status thresholds and overspend detection
- PASS: unbudgeted spending counts against total
- PASS: zero budget is safe

### dashboard.tests.CalculationTests
- PASS: available balance formula
- PASS: decimal precision no float errors
- PASS: negative balance allowed and flagged
- PASS: period filters use correct dates
- PASS: rounding half up
- PASS: week and month ranges
- PASS: zero data everywhere

### dashboard.tests.DashboardViewTests
- PASS: all report kinds render and use own data
- PASS: cards and charts use actual records
- PASS: custom 404 page
- PASS: dashboard only shows own data
- PASS: empty state for new student
- PASS: quick add button present on dashboard

### expenses.tests.ExpenseTests
- PASS: add expense and balance updates automatically
- PASS: custom category usable and private
- PASS: daily view previous day
- PASS: date defaults to today and other dates allowed
- PASS: duplicate submission blocked but different expense allowed
- PASS: edit and delete
- PASS: filters and search
- PASS: isolation
- PASS: multiple expenses same day and daily total
- PASS: overspending is recorded and flagged
- PASS: unsafe next redirect ignored
- PASS: validation blocks bad data
- PASS: weekly and monthly totals

### income.tests.IncomeTests
- PASS: add income
- PASS: cannot use expense category as income source
- PASS: custom income source
- PASS: delete requires confirmation then removes
- PASS: edit income
- PASS: filter by source and date
- PASS: irregular income and total only counts recorded
- PASS: isolation
- PASS: rejects zero negative and future dates

### savings.tests.SavingsTests
- PASS: contribution validation
- PASS: contributions update progress and history
- PASS: create goal
- PASS: edit and delete contribution recalculate
- PASS: goal complete and progress capped
- PASS: goal validation
- PASS: isolation
- PASS: progress example from spec
- PASS: savings not double counted

## Coverage of the required test areas
- **Authentication:** registration, login, logout, bad login, password reset email, every private page redirects when logged out.
- **Income:** add, edit, delete (with confirmation), totals incl. irregular income, validation, filters, custom sources.
- **Budgets:** create, duplicate month blocked, allocations, remaining/utilization (spec example 2,500 → 1,800 spent → 700 left), overspend detection, zero budget, copy previous.
- **Daily expenses:** multiple per day, edit, delete, daily totals (spec example KSh 500), weekly/monthly totals, automatic balance (5,000 → 4,800 pattern), duplicate protection, overspending recorded and flagged.
- **Savings:** goal creation, contributions, progress (spec example 40%), no double counting, edit/delete recalculation.
- **Dashboard:** cards and chart data from real records, own-data-only, all 7 reports render, Decimal precision (0.10 + 0.20 = 0.30), empty-state and zero-data handling.
- **Security / isolation:** every module returns 404 for another student's records and never changes them; unsafe redirects ignored.
- **Advisor:** each rule fires only with enough data; tips use only the student's own records.

## Other checks performed
- Smoke test: 36 pages/URLs (all CRUD pages, 7 report kinds, filters) returned HTTP 200 for a demo student.
- `python manage.py check` and `makemigrations --check`: no issues, no missing migrations.
- `check --deploy` with `DJANGO_DEBUG=False`: only optional HSTS subdomain/preload advisories remain.
- Not done here: visual review in a real browser, and load testing. Please click through the app once before your demonstration.
