"""Owner's 'download everything' Excel export (open-format data ownership)."""
import datetime

from django.utils import timezone

from cashbook.models import CashBookEntry, DayClose
from core.exporting import xlsx_response
from core.models import GoldRate, HeadOfAccount
from investors.models import Investor, InvestorTransaction
from parties.models import Customer, Supplier, SupplierTransaction
from refining.models import RefineLot
from sales.models import Invoice, OldGoldIntake, Payment, SaleLine
from stock.models import StockItem

MODELS = [
    ("Stock", StockItem), ("Customers", Customer), ("Suppliers", Supplier),
    ("Supplier ledger", SupplierTransaction), ("Invoices", Invoice), ("Sale lines", SaleLine),
    ("Payments", Payment), ("Old gold", OldGoldIntake), ("Cash book", CashBookEntry), ("Day close", DayClose),
    ("Heads of account", HeadOfAccount), ("Gold rates", GoldRate), ("Refine lots", RefineLot),
    ("Investors", Investor), ("Investor txns", InvestorTransaction),
]


def _plain(value):
    if isinstance(value, datetime.datetime):
        return timezone.localtime(value).replace(tzinfo=None) if timezone.is_aware(value) else value
    if isinstance(value, (dict, list)):
        return str(value)
    if value is not None and not isinstance(value, (int, float, str, bool, datetime.date)):
        return str(value)
    return value


def build_sheets():
    sheets = []
    for title, model in MODELS:
        fields = [f for f in model._meta.concrete_fields]
        columns = [(f.attname, f.verbose_name.title()) for f in fields]
        rows = [{k: _plain(v) for k, v in row.items()} for row in model.objects.values(*[f.attname for f in fields])]
        sheets.append({"title": title, "columns": columns, "rows": rows})
    return sheets


def full_workbook_response():
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    return xlsx_response(f"al-noor-full-export-{stamp}", build_sheets())
