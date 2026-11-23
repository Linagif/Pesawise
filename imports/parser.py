"""M-Pesa confirmation SMS parser.

Design rules
  * Only extract what the message clearly says. Anything not recognised is reported as 'not understood': never guessed.
  * Data minimisation: the parser keeps amount, fee, counterparty NAME, date/time, reference code (and the code a reversal
    refers to). It drops phone numbers, account numbers, the M-Pesa balance and the original message text.
  * Pure functions with no database access, so they are easy to test.
"""
import re
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal, InvalidOperation

from django.utils import timezone

SENT, PAID, PAYBILL, RECEIVED, WITHDRAW, DEPOSIT, AIRTIME, REVERSAL = (
    "SENT", "PAID", "PAYBILL", "RECEIVED", "WITHDRAW", "DEPOSIT", "AIRTIME", "REVERSAL")

MAX_CHARS = 20000
MAX_MESSAGES = 200
MAX_AMOUNT = Decimal("10000000")

_CODE = r"[A-Z0-9]{10}"
_AMT = r"(?:Ksh|KES)\.?\s?([\d,]+(?:\.\d{1,2})?)"
_PHONE = r"[0-9*+]{7,15}"
_SPLIT = re.compile(rf"(?=\b{_CODE}\s+[Cc]onfirmed)")
_HEAD = re.compile(rf"^({_CODE})\s+[Cc]onfirmed\b")
_DATE = re.compile(r"\bon\s+(\d{1,2})/(\d{1,2})/(\d{2,4})\s+at\s+(\d{1,2}):(\d{2})\s?([AaPp][Mm])", re.I)
_FEE = re.compile(rf"Transaction cost,?\s*{_AMT}", re.I)

_PATTERNS = [   # order matters: more specific patterns first
    (REVERSAL, re.compile(rf"Reversal of transaction ({_CODE})", re.I)),
    (RECEIVED, re.compile(rf"You have received {_AMT} from (?P<name>.+?)(?:\s+{_PHONE})?\s+on\s+\d", re.I)),
    (AIRTIME, re.compile(rf"You bought {_AMT} of airtime", re.I)),
    (WITHDRAW, re.compile(rf"Withdraw {_AMT} from (?P<name>.+?)\s+New M-PESA", re.I)),
    (DEPOSIT, re.compile(rf"Give {_AMT} cash to (?P<name>.+?)\s+New M-PESA", re.I)),
    (PAYBILL, re.compile(rf"{_AMT} sent to (?P<name>.+?) for account (?P<acc>.+?) on\s+\d", re.I)),
    (PAID, re.compile(rf"{_AMT} paid to (?P<name>.+?)\.?\s+on\s+\d", re.I)),
    (SENT, re.compile(rf"{_AMT} sent to (?P<name>.+?)(?:\s+{_PHONE})?\s*\.?\s+on\s+\d", re.I)),
]


class ParseError(ValueError):
    pass


@dataclass
class ParsedMessage:
    reference: str
    kind: str
    amount: Decimal
    charge: Decimal
    counterparty: str
    occurred_on: date
    occurred_time: time | None
    reversal_of: str = ""


def _money(text):
    try:
        return Decimal(text.replace(",", "")).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ParseError("Could not read an amount.") from exc


def _clean_name(name):
    name = re.sub(rf"{_PHONE}", "", name or "")                # never keep phone numbers
    name = re.sub(r"^\d+\s*-\s*", "", name.strip())              # agent/till number prefix, e.g. '123456 - NAME'
    return re.sub(r"\s+", " ", name).strip(" .-")[:120]


def split_messages(text):
    text = (text or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in _SPLIT.split(text) if p.strip()]
    return parts or [text]


def parse_message(raw, today=None):
    today = today or timezone.localdate()
    text = re.sub(r"\s+", " ", raw.strip())
    head = _HEAD.match(text)
    if not head:
        raise ParseError("Not an M-Pesa confirmation message.")
    reference = head.group(1)
    kind = match = None
    for k, rx in _PATTERNS:
        match = rx.search(text)
        if match:
            kind = k
            break
    if not kind:
        raise ParseError("This type of message is not supported yet.")

    reversal_of = ""
    if kind == REVERSAL:
        reversal_of = match.group(1)
        credited = re.search(rf"and\s+{_AMT}\s+is credited", text, re.I)
        if not credited:
            raise ParseError("Could not find the reversed amount.")
        amount, name = _money(credited.group(1)), ""
    else:
        amount = _money(match.group(1))
        name = _clean_name(match.groupdict().get("name")) if "name" in match.groupdict() else ""
        if kind == AIRTIME:
            name = "Airtime"
    if amount <= 0 or amount > MAX_AMOUNT:
        raise ParseError("The amount is not valid.")
    fee = _FEE.search(text)
    charge = _money(fee.group(1)) if fee else Decimal("0.00")

    d = _DATE.search(text)
    if not d:
        raise ParseError("Could not find the date and time.")
    day, month, year, hour, minute, ampm = int(d[1]), int(d[2]), int(d[3]), int(d[4]), int(d[5]), d[6].upper()
    year += 2000 if year < 100 else 0
    try:
        occurred_on = date(year, month, day)
        hour24 = hour % 12 + (12 if ampm == "PM" else 0)
        occurred_time = time(hour24, minute)
    except ValueError as exc:
        raise ParseError("The date or time is not valid.") from exc
    if occurred_on > today:
        raise ParseError("The date is in the future.")
    return ParsedMessage(reference, kind, amount, charge, name, occurred_on, occurred_time, reversal_of)


def parse_many(text, today=None):
    """Returns (parsed_messages, not_understood_count). Never raises for bad content."""
    parsed, bad = [], 0
    chunks = split_messages(text)[:MAX_MESSAGES]
    for chunk in chunks:
        try:
            parsed.append(parse_message(chunk, today))
        except ParseError:
            bad += 1
    return parsed, bad
