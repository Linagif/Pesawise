# PesaWise: Test Results

Run with `python manage.py test -v 2`.

**Result: 246 of 246 tests passed.**

| Test class | Tests |
|---|---:|
| accounts.test_demo.DemoDataQualityTests | 4 |
| accounts.test_demo.DemoSwitchTests | 2 |
| accounts.test_demo.VisitorDemoTests | 7 |
| accounts.tests.AccessControlTests | 2 |
| accounts.tests.ProfileTests | 2 |
| accounts.tests.RegistrationLoginTests | 5 |
| advisor.test_analysis.CashFlowTests | 3 |
| advisor.test_analysis.CategoryChangeTests | 5 |
| advisor.test_analysis.EmergencyFundTests | 4 |
| advisor.test_analysis.HealthPageTests | 2 |
| advisor.test_analysis.HealthReportTests | 6 |
| advisor.test_analysis.HelperTests | 3 |
| advisor.test_analysis.RecurringTests | 5 |
| advisor.test_analysis.SmallPurchaseTests | 2 |
| advisor.test_analysis.SplitTests | 2 |
| advisor.test_recommendations.LifecycleTests | 6 |
| advisor.test_recommendations.OutcomeTests | 5 |
| advisor.test_recommendations.RuleTests | 14 |
| advisor.test_recommendations.ViewTests | 7 |
| advisor.test_simulator.AffordTests | 6 |
| advisor.test_simulator.BaselineTests | 4 |
| advisor.test_simulator.CutTests | 4 |
| advisor.test_simulator.IncomeChangeTests | 5 |
| advisor.test_simulator.SavePlanTests | 5 |
| advisor.test_simulator.SimulatorPageTests | 7 |
| advisor.tests.AdvisorTests | 8 |
| budgets.tests.BudgetTests | 11 |
| core.test_pwa.ManifestTests | 5 |
| core.test_pwa.ServiceWorkerBehaviourTests | 7 |
| core.test_pwa.ServiceWorkerFileTests | 4 |
| dashboard.tests.CalculationTests | 7 |
| dashboard.tests.DashboardViewTests | 7 |
| dashboard.tests.ExportTests | 8 |
| expenses.tests.ExpenseTests | 13 |
| imports.tests.ImportServiceTests | 5 |
| imports.tests.ImportViewTests | 6 |
| imports.tests.ParserTests | 12 |
| imports.tests.ReviewWorkflowTests | 15 |
| income.tests.IncomeTests | 9 |
| savings.tests.SavingsTests | 9 |

## Detail

### accounts.test_demo.DemoDataQualityTests
- PASS: health indicators all available
- PASS: recommendations are sensible
- PASS: review queue has three waiting messages and no dates in future
- PASS: simulator has a baseline

### accounts.test_demo.DemoSwitchTests
- PASS: button shown when enabled
- PASS: off by default in production like settings

### accounts.test_demo.VisitorDemoTests
- PASS: banner shown only for demo accounts
- PASS: cannot log in to a demo account with any password
- PASS: capacity cap
- PASS: creates private logged in sandbox with data
- PASS: each visitor gets separate data
- PASS: expired demos are purged but real accounts never
- PASS: requires post and csrf safe method only

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

### advisor.test_analysis.CashFlowTests
- PASS: isolated from other students
- PASS: net cash flow and savings rate
- PASS: no income means no savings rate

### advisor.test_analysis.CategoryChangeTests
- PASS: current partial month is never compared
- PASS: flags large rise with exact figures
- PASS: ignores small percent and small amount changes
- PASS: needs two full months
- PASS: new and falling categories

### advisor.test_analysis.EmergencyFundTests
- PASS: average over several months and discretionary ignored
- PASS: months of cover
- PASS: none without a complete month of essentials
- PASS: zero savings is zero months

### advisor.test_analysis.HealthPageTests
- PASS: page renders both periods with disclaimer
- PASS: page shows alerts section and requires login

### advisor.test_analysis.HealthReportTests
- PASS: empty account has no numbers and a notice
- PASS: insight text contains real figures
- PASS: last month period
- PASS: negative cash flow is flagged
- PASS: report never includes other students data
- PASS: savings rate statuses

### advisor.test_analysis.HelperTests
- PASS: custom category defaults to discretionary and can be essential
- PASS: default categories are classified
- PASS: pct rounding and zero whole

### advisor.test_analysis.RecurringTests
- PASS: detects monthly subscription
- PASS: essential bill is labelled and worded differently
- PASS: frequent daily purchases are not flagged
- PASS: two months is not enough
- PASS: varying amounts are not recurring

### advisor.test_analysis.SmallPurchaseTests
- PASS: does not fire below threshold
- PASS: fires at threshold and reports facts

### advisor.test_analysis.SplitTests
- PASS: essential vs discretionary shares
- PASS: no spending gives no shares

### advisor.test_recommendations.LifecycleTests
- PASS: accepted stays active even when trigger goes away
- PASS: dismissed is not resurfaced during cooldown but returns after
- PASS: pending refreshes with new numbers but accepted is untouched
- PASS: recommendations are per student
- PASS: refresh is idempotent and sets dates
- PASS: untriggered pending becomes inactive

### advisor.test_recommendations.OutcomeTests
- PASS: higher spending reported
- PASS: lower spending reported with causation caveat
- PASS: no outcome without category or when not accepted
- PASS: outcome only counts own spending
- PASS: too early

### advisor.test_recommendations.RuleTests
- PASS: category rise discretionary has amount essential does not
- PASS: confidence grows with history
- PASS: emergency fund recommendation figures
- PASS: essential recurring payments never get a stop it recommendation
- PASS: negative cashflow recommendation
- PASS: negative cashflow without discretionary spending has no amount
- PASS: never suggests more than half of free cash
- PASS: no savings rate recommendation when already saving enough
- PASS: no savings suggestion when there is no free cash
- PASS: nothing without a full month of history
- PASS: recurring payment recommendation
- PASS: round50 helper
- PASS: savings rate recommendation when no essential history
- PASS: small purchase weekly limit

### advisor.test_recommendations.ViewTests
- PASS: cannot touch another students recommendation
- PASS: feedback
- PASS: health page links with pending count
- PASS: invalid status is rejected
- PASS: page shows evidence and all required parts
- PASS: status change requires post and login
- PASS: status workflow

### advisor.test_simulator.AffordTests
- PASS: deadline modes
- PASS: laptop example is not supported
- PASS: no free cash cannot close gap
- PASS: pay now good when buffer kept
- PASS: pay now tight when buffer lost
- PASS: shortfall closed quickly

### advisor.test_simulator.BaselineTests
- PASS: baseline averages several months
- PASS: baseline figures
- PASS: baseline ignores other students and current month
- PASS: baseline none without a complete month

### advisor.test_simulator.CutTests
- PASS: bigger cuts get harder verdicts
- PASS: category with no spending
- PASS: cut capped at what you spend
- PASS: small cut is realistic

### advisor.test_simulator.IncomeChangeTests
- PASS: break even is tight
- PASS: cannot go below zero income
- PASS: deficit and how long balance lasts
- PASS: increase by amount
- PASS: twenty percent fall

### advisor.test_simulator.SavePlanTests
- PASS: monthly feasibility
- PASS: no surplus gives no date
- PASS: target already met
- PASS: target only uses surplus as pace
- PASS: time to target and alternatives

### advisor.test_simulator.SimulatorPageTests
- PASS: cannot simulate with another students category
- PASS: each scenario runs end to end
- PASS: health page links to simulator
- PASS: invalid input shows errors and no result
- PASS: renders without enough history
- PASS: requires login
- PASS: simulating never changes data

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

### core.test_pwa.ManifestTests
- PASS: icons exist with the declared sizes
- PASS: post not allowed
- PASS: required installability fields
- PASS: served publicly with the right type
- PASS: shortcuts point to real pages

### core.test_pwa.ServiceWorkerBehaviourTests
- PASS: downloads and data requests are not handled or cached
- PASS: installs the offline page and icons
- PASS: never intercepts form posts or other sites
- PASS: offline navigation shows the offline page not stale data
- PASS: old versions are cleaned but other caches untouched
- PASS: pages come from the network and are never stored
- PASS: static files are cached and work offline

### core.test_pwa.ServiceWorkerFileTests
- PASS: headers allow root scope and prompt updates
- PASS: install button and instructions for signed in students
- PASS: offline page is public and self contained
- PASS: pages link the manifest and script

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
- PASS: impossible dates in url do not crash
- PASS: quick add button present on dashboard

### dashboard.tests.ExportTests
- PASS: csv download headers and content
- PASS: csv for every report kind
- PASS: csv neutralises formula injection
- PASS: export respects period and bad input
- PASS: exports require login
- PASS: pdf is a real pdf for every kind
- PASS: pdf survives special characters
- PASS: report page has download buttons keeping filters

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

### imports.tests.ImportServiceTests
- PASS: paste creates pending rows only
- PASS: repasting never duplicates
- PASS: same reference is allowed for different students
- PASS: saved after review even after it was skipped cannot be reimported
- PASS: stored row has no phone balance or raw text

### imports.tests.ImportViewTests
- PASS: empty paste rejected
- PASS: other students rows are invisible and untouchable
- PASS: oversized paste rejected
- PASS: pages require login and post
- PASS: paste flow end to end
- PASS: safety notice is shown

### imports.tests.ParserTests
- PASS: airtime and reversal
- PASS: future and invalid dates refused
- PASS: message cap
- PASS: no phone numbers or balances kept
- PASS: paid to till zero charge
- PASS: paybill keeps name not account number
- PASS: received with masked phone
- PASS: sent to person
- PASS: split many messages and count unreadable
- PASS: two digit year and today injection
- PASS: unsupported and garbage messages are refused not guessed
- PASS: withdraw and deposit

### imports.tests.ReviewWorkflowTests
- PASS: airtime is preselected but unknown recipient is not
- PASS: category remembered for same recipient after confirmation
- PASS: deposit without fee creates nothing but is marked done
- PASS: discard removes pending only
- PASS: income saved with chosen source
- PASS: nothing is saved without a choice or with later
- PASS: possible duplicate of manual entry is flagged
- PASS: remembered category is not shared between students
- PASS: reversal restores balance without deleting original
- PASS: save expense with exact values and separate fee
- PASS: save without category stays pending with error
- PASS: second application of same row cannot double save
- PASS: skip creates no records
- PASS: withdrawal is not spending only the fee is
- PASS: wrong category type or other students category rejected

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

## Other checks
- `python manage.py check` and `makemigrations --check`: no issues.
- The whole suite also passes against PostgreSQL 16 (CI runs both SQLite and PostgreSQL).
- The service-worker tests run the real worker in Node. Deliberately breaking it (caching pages, intercepting POSTs) makes them fail.
- All test data is invented. No real names, phone numbers or M-Pesa messages are used.
- Not covered here: visual review on real phones, load testing, and real-message parser validation. Check these manually.
