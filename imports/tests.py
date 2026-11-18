"""Tests use INVENTED names, codes and numbers only (no real customer data)."""
from datetime import date, time
from decimal import Decimal as D

from django.urls import reverse

from core.models import Category
from core.testing import BaseTestCase, cat
from dashboard import services as svc
from expenses.models import Expense
from imports import parser as p
from imports import services as isvc
from imports.models import ImportedTransaction as IT
from income.models import Income

SENT = ("QAB1C2D3E4 Confirmed. Ksh850.00 sent to JOHN KAMAU 0712345678 on 14/11/25 at 2:15 PM. New M-PESA balance is "
        "Ksh1,234.56. Transaction cost, Ksh7.00. Amount you can transact within the day is 499,150.00.")
RECEIVED = ("QAB1C2D3E5 Confirmed.You have received Ksh1,000.00 from JANE WANJIKU 0722***456 on 14/11/25 at 9:05 AM  "
            "New M-PESA balance is Ksh2,234.56. Separate personal and business funds through Pochi la Biashara on *334#.")
PAID = ("QAB1C2D3E6 Confirmed. Ksh350.00 paid to FRESHMART SUPERMARKET. on 14/11/25 at 6:30 PM.New M-PESA balance is "
        "Ksh884.56. Transaction cost, Ksh0.00.")
PAYBILL = ("QAB1C2D3E7 Confirmed. Ksh500.00 sent to KPLC PREPAID for account 12345678 on 14/11/25 at 7:00 PM New M-PESA "
           "balance is Ksh384.56. Transaction cost, Ksh5.00.")
WITHDRAW = ("QAB1C2D3E8 Confirmed. on 14/11/25 at 8:10 AM Withdraw Ksh1,000.00 from 123456 - TEST AGENT NAIROBI New M-PESA "
            "balance is Ksh100.00. Transaction cost, Ksh28.00.")
DEPOSIT = ("QAB1C2D3E9 Confirmed. On 14/11/25 at 12:10 AM Give Ksh1,000.00 cash to TEST AGENT - NAIROBI New M-PESA balance "
           "is Ksh1,100.00.")
AIRTIME = ("QAB1C2D3F1 confirmed. You bought Ksh50.00 of airtime on 14/11/25 at 8:10 AM.New M-PESA balance is Ksh1,050.00. "
           "Transaction cost, Ksh0.00.")
REVERSAL = ("QAB1C2D3F2 Confirmed. Reversal of transaction QAB1C2D3E4 has been successfully reversed on 14/11/25 at 3:00 PM "
            "and Ksh850.00 is credited to your M-PESA account. New M-PESA balance is Ksh2,084.56.")
FULIZA = "QAB1C2D3F3 Confirmed. Fuliza M-PESA amount is Ksh 100.00. on 14/11/25 at 3:00 PM"


class ParserTests(BaseTestCase):
    def test_sent_to_person(self):
        m = p.parse_message(SENT)
        self.assertEqual((m.reference, m.kind, m.amount, m.charge, m.counterparty),
                         ("QAB1C2D3E4", p.SENT, D("850.00"), D("7.00"), "JOHN KAMAU"))
        self.assertEqual((m.occurred_on, m.occurred_time), (date(2025, 11, 14), time(14, 15)))

    def test_received_with_masked_phone(self):
        m = p.parse_message(RECEIVED)
        self.assertEqual((m.kind, m.amount, m.counterparty), (p.RECEIVED, D("1000.00"), "JANE WANJIKU"))

    def test_paid_to_till_zero_charge(self):
        m = p.parse_message(PAID)
        self.assertEqual((m.kind, m.counterparty, m.charge), (p.PAID, "FRESHMART SUPERMARKET", D("0.00")))

    def test_paybill_keeps_name_not_account_number(self):
        m = p.parse_message(PAYBILL)
        self.assertEqual((m.kind, m.counterparty, m.charge), (p.PAYBILL, "KPLC PREPAID", D("5.00")))
        self.assertNotIn("12345678", repr(m))

    def test_withdraw_and_deposit(self):
        w, d = p.parse_message(WITHDRAW), p.parse_message(DEPOSIT)
        self.assertEqual((w.kind, w.amount, w.charge, w.counterparty), (p.WITHDRAW, D("1000.00"), D("28.00"), "TEST AGENT NAIROBI"))
        self.assertEqual((d.kind, d.occurred_time), (p.DEPOSIT, time(0, 10)))      # 12:10 AM -> 00:10

    def test_airtime_and_reversal(self):
        a, r = p.parse_message(AIRTIME), p.parse_message(REVERSAL)
        self.assertEqual((a.kind, a.counterparty), (p.AIRTIME, "Airtime"))
        self.assertEqual((r.kind, r.amount, r.reversal_of), (p.REVERSAL, D("850.00"), "QAB1C2D3E4"))

    def test_no_phone_numbers_or_balances_kept(self):
        for text in (SENT, RECEIVED, PAID, PAYBILL, WITHDRAW):
            m = p.parse_message(text)
            blob = repr(m)
            self.assertNotRegex(blob, r"\d{7,}")                                   # no phone/account numbers
            self.assertNotIn("1,234.56", blob); self.assertNotIn("234.56", blob)   # no balances

    def test_unsupported_and_garbage_messages_are_refused_not_guessed(self):
        for bad in (FULIZA, "hello", "Your OTP is 123456", ""):
            with self.assertRaises(p.ParseError):
                p.parse_message(bad)

    def test_future_and_invalid_dates_refused(self):
        with self.assertRaises(p.ParseError):
            p.parse_message(SENT.replace("14/11/25", "14/11/45"))
        with self.assertRaises(p.ParseError):
            p.parse_message(SENT.replace("14/11/25", "31/02/25"))
        self.assertEqual(p.parse_message(SENT.replace("14/11/25", "14/11/2025")).occurred_on, date(2025, 11, 14))

    def test_two_digit_year_and_today_injection(self):
        self.assertEqual(p.parse_message(SENT.replace("14/11/25", "01/12/26"), today=date(2026, 12, 1)).occurred_on, date(2026, 12, 1))

    def test_split_many_messages_and_count_unreadable(self):
        parsed, bad = p.parse_many("\n\n".join([SENT, RECEIVED, FULIZA, PAID]))
        self.assertEqual(([m.kind for m in parsed], bad), ([p.SENT, p.RECEIVED, p.PAID], 1))

    def test_message_cap(self):
        many = "\n\n".join(SENT.replace("QAB1C2D3E4", f"Q{n:09d}") for n in range(250))
        parsed, bad = p.parse_many(many)
        self.assertEqual((len(parsed), bad), (p.MAX_MESSAGES, 0))


class ImportServiceTests(BaseTestCase):
    def test_paste_creates_pending_rows_only(self):
        r = isvc.import_text(self.user, "\n\n".join([SENT, RECEIVED, FULIZA]))
        self.assertEqual(r, {"new": 2, "duplicates": 0, "not_understood": 1})
        self.assertEqual(IT.objects.filter(user=self.user, status="PENDING").count(), 2)
        self.assertEqual((Expense.objects.count(), Income.objects.count()), (0, 0))      # nothing is real yet

    def test_repasting_never_duplicates(self):
        isvc.import_text(self.user, SENT)
        r = isvc.import_text(self.user, SENT + "\n\n" + SENT)
        self.assertEqual((r["new"], r["duplicates"]), (0, 2))
        self.assertEqual(IT.objects.count(), 1)

    def test_same_reference_is_allowed_for_different_students(self):
        isvc.import_text(self.user, SENT); isvc.import_text(self.other, SENT)
        self.assertEqual(IT.objects.count(), 2)

    def test_stored_row_has_no_phone_balance_or_raw_text(self):
        isvc.import_text(self.user, SENT)
        row = IT.objects.get()
        stored = " ".join(str(getattr(row, f.name)) for f in IT._meta.fields)
        self.assertNotIn("0712345678", stored); self.assertNotIn("1,234", stored); self.assertNotIn("Confirmed", stored)

    def test_saved_after_review_even_after_it_was_skipped_cannot_be_reimported(self):
        isvc.import_text(self.user, SENT)
        row = IT.objects.get()
        isvc.apply_review(self.user, {f"action_{row.pk}": "skip"})
        self.assertEqual(isvc.import_text(self.user, SENT)["duplicates"], 1)


class ReviewWorkflowTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.food = cat("Food").pk

    def row(self, ref):
        return IT.objects.get(user=self.user, reference=ref)

    def review(self, decisions):
        data = {}
        for ref, (action, category) in decisions.items():
            pk = self.row(ref).pk
            data[f"action_{pk}"] = action
            if category:
                data[f"category_{pk}"] = category
        return self.client.post(reverse("imports:review"), data, follow=True)

    def test_save_expense_with_exact_values_and_separate_fee(self):
        isvc.import_text(self.user, SENT)
        self.review({"QAB1C2D3E4": ("save", self.food)})
        e = Expense.objects.get(description="Sent to JOHN KAMAU")
        self.assertEqual((e.amount, e.expense_date, e.category.name, e.payment_method, e.user), (D("850.00"), date(2025, 11, 14), "Food", "MPESA", self.user))
        fee = Expense.objects.get(description__startswith="M-Pesa charge")
        self.assertEqual((fee.amount, fee.category.name), (D("7.00"), "Transaction charges"))
        self.assertEqual(self.row("QAB1C2D3E4").status, "IMPORTED")
        self.assertEqual(svc.total_expenses(self.user), D("857.00"))

    def test_nothing_is_saved_without_a_choice_or_with_later(self):
        isvc.import_text(self.user, SENT)
        self.review({"QAB1C2D3E4": ("later", self.food)})
        self.assertEqual(Expense.objects.count(), 0)
        self.assertEqual(self.row("QAB1C2D3E4").status, "PENDING")

    def test_save_without_category_stays_pending_with_error(self):
        isvc.import_text(self.user, SENT)
        r = self.review({"QAB1C2D3E4": ("save", "")})
        self.assertEqual((Expense.objects.count(), self.row("QAB1C2D3E4").status), (0, "PENDING"))
        self.assertContains(r, "Choose a category")

    def test_skip_creates_no_records(self):
        isvc.import_text(self.user, SENT)
        self.review({"QAB1C2D3E4": ("skip", None)})
        self.assertEqual((Expense.objects.count(), self.row("QAB1C2D3E4").status), (0, "SKIPPED"))

    def test_income_saved_with_chosen_source(self):
        isvc.import_text(self.user, RECEIVED)
        self.review({"QAB1C2D3E5": ("save", cat("Casual jobs", "INCOME").pk)})
        i = Income.objects.get()
        self.assertEqual((i.amount, i.source.name, i.date_received, i.description), (D("1000.00"), "Casual jobs", date(2025, 11, 14), "Received from JANE WANJIKU"))

    def test_withdrawal_is_not_spending_only_the_fee_is(self):
        isvc.import_text(self.user, WITHDRAW)
        self.review({"QAB1C2D3E8": ("save", None)})
        self.assertEqual([e.amount for e in Expense.objects.all()], [D("28.00")])
        self.assertEqual(Income.objects.count(), 0)

    def test_deposit_without_fee_creates_nothing_but_is_marked_done(self):
        isvc.import_text(self.user, DEPOSIT)
        self.review({"QAB1C2D3E9": ("save", None)})
        self.assertEqual((Expense.objects.count(), Income.objects.count(), self.row("QAB1C2D3E9").status), (0, 0, "IMPORTED"))

    def test_reversal_restores_balance_without_deleting_original(self):
        self.income(5000)
        isvc.import_text(self.user, SENT + "\n\n" + REVERSAL)
        self.review({"QAB1C2D3E4": ("save", self.food)})
        self.assertEqual(svc.available_balance(self.user), D("5000.00") - D("857.00"))
        self.review({"QAB1C2D3F2": ("save", cat("Other", "INCOME").pk)})
        self.assertEqual(svc.available_balance(self.user), D("4143.00") + D("850.00"))      # only the fee stays lost
        self.assertEqual(Expense.objects.filter(description="Sent to JOHN KAMAU").count(), 1)   # original kept

    def test_airtime_is_preselected_but_unknown_recipient_is_not(self):
        isvc.import_text(self.user, AIRTIME + "\n\n" + SENT)
        rows = {i["row"].reference: i for i in isvc.pending_rows(self.user)}
        self.assertEqual(rows["QAB1C2D3F1"]["suggested"].name, "Internet and airtime")
        self.assertIsNone(rows["QAB1C2D3E4"]["suggested"])                       # a personal transfer is never guessed

    def test_category_remembered_for_same_recipient_after_confirmation(self):
        isvc.import_text(self.user, PAID)
        self.review({"QAB1C2D3E6": ("save", self.food)})
        later = PAID.replace("QAB1C2D3E6", "QAB1C2D3G6")
        isvc.import_text(self.user, later)
        s = {i["row"].reference: i for i in isvc.pending_rows(self.user)}["QAB1C2D3G6"]
        self.assertEqual(s["suggested"].name, "Food")
        self.assertIn("before", s["reason"])

    def test_remembered_category_is_not_shared_between_students(self):
        isvc.import_text(self.other, PAID)
        row = IT.objects.get(user=self.other); isvc.apply_review(self.other, {f"action_{row.pk}": "save", f"category_{row.pk}": self.food})
        isvc.import_text(self.user, PAID)
        self.assertIsNone(isvc.pending_rows(self.user)[0]["suggested"])

    def test_possible_duplicate_of_manual_entry_is_flagged(self):
        self.expense(850, day=date(2025, 11, 14), desc="fare")
        isvc.import_text(self.user, SENT)
        self.assertTrue(isvc.pending_rows(self.user)[0]["duplicate"])

    def test_wrong_category_type_or_other_students_category_rejected(self):
        theirs = Category.objects.create(user=self.other, name="BobCat", category_type="EXPENSE")
        isvc.import_text(self.user, SENT)
        for bad in (cat("Casual jobs", "INCOME").pk, theirs.pk, 999999, "abc"):
            self.review({"QAB1C2D3E4": ("save", bad)})
        self.assertEqual((Expense.objects.count(), self.row("QAB1C2D3E4").status), (0, "PENDING"))

    def test_second_application_of_same_row_cannot_double_save(self):
        isvc.import_text(self.user, SENT)
        row = self.row("QAB1C2D3E4")
        data = {f"action_{row.pk}": "save", f"category_{row.pk}": self.food}
        self.client.post(reverse("imports:review"), data); self.client.post(reverse("imports:review"), data)
        self.assertEqual(Expense.objects.filter(description="Sent to JOHN KAMAU").count(), 1)

    def test_discard_removes_pending_only(self):
        isvc.import_text(self.user, SENT + "\n\n" + PAID)
        self.review({"QAB1C2D3E6": ("save", self.food)})
        self.client.post(reverse("imports:discard"))
        self.assertEqual(list(IT.objects.values_list("reference", "status")), [("QAB1C2D3E6", "IMPORTED")])


class ImportViewTests(BaseTestCase):
    def test_pages_require_login_and_post(self):
        self.client.logout()
        for name in ("imports:paste", "imports:review"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)
        self.assertEqual(self.client.post(reverse("imports:discard")).status_code, 302)
        self.client.login(username="alice", password=self.PASSWORD)
        self.assertEqual(self.client.get(reverse("imports:discard")).status_code, 405)

    def test_paste_flow_end_to_end(self):
        r = self.client.post(reverse("imports:paste"), {"text": SENT + "\n\n" + PAID + "\n\n" + FULIZA}, follow=True)
        self.assertRedirects(r, reverse("imports:review"))
        self.assertContains(r, "2 new messages ready to review")
        self.assertContains(r, "1 message was not understood")
        self.assertContains(r, "JOHN KAMAU")

    def test_oversized_paste_rejected(self):
        r = self.client.post(reverse("imports:paste"), {"text": "x" * (p.MAX_CHARS + 1)})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(IT.objects.count(), 0)

    def test_empty_paste_rejected(self):
        self.assertEqual(self.client.post(reverse("imports:paste"), {"text": "   "}).status_code, 200)

    def test_other_students_rows_are_invisible_and_untouchable(self):
        isvc.import_text(self.other, SENT)
        theirs = IT.objects.get(user=self.other)
        r = self.client.get(reverse("imports:review"))
        self.assertNotContains(r, "JOHN KAMAU")
        self.client.post(reverse("imports:review"), {f"action_{theirs.pk}": "save", f"category_{theirs.pk}": cat("Food").pk})
        self.client.post(reverse("imports:discard"))
        theirs.refresh_from_db()
        self.assertEqual((theirs.status, Expense.objects.count()), ("PENDING", 0))

    def test_safety_notice_is_shown(self):
        self.assertContains(self.client.get(reverse("imports:paste")), "never ask for your M-Pesa PIN")
