import re

from django.db import transaction
from django.utils import timezone

from core.exceptions import BusinessRuleError
from core.models import Sequence, ShopSettings
from parties.models import SupplierTransaction

from .models import StockItem

CODE_DIGITS = 4


def prefix_for(category):
    prefixes = ShopSettings.load().code_prefixes
    for cat, prefix in prefixes.items():
        if cat.lower() == (category or "").strip().lower():
            return prefix.upper()
    raise BusinessRuleError(
        f"No code prefix is set for category '{category}'. Add it under Settings > Code prefixes."
    )


def _existing_max(prefix):
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    best = 0
    for code in StockItem.objects.filter(code__startswith=prefix).values_list("code", flat=True).iterator():
        m = pattern.match(code)
        if m:
            best = max(best, int(m.group(1)))
    return best


def _format(prefix, number):
    return f"{prefix}{number:0{CODE_DIGITS}d}"


def preview_code(category):
    prefix = prefix_for(category)
    return _format(prefix, Sequence.peek(f"code:{prefix}", floor=_existing_max(prefix)))


def next_code(category):
    prefix = prefix_for(category)
    for _ in range(20):
        code = _format(prefix, Sequence.next_value(f"code:{prefix}", floor=_existing_max(prefix)))
        if not StockItem.objects.filter(code=code).exists():
            return code
    raise BusinessRuleError("Could not generate a unique item code; please try again.")


def bump_sequence_for(code):
    """After an explicit/imported code, make sure the counter never re-issues it."""
    m = re.match(r"^([A-Z]+)(\d+)$", code or "")
    if not m:
        return
    with transaction.atomic():
        seq, _ = Sequence.objects.select_for_update().get_or_create(name=f"code:{m.group(1)}")
        if int(m.group(2)) > seq.last_value:
            seq.last_value = int(m.group(2))
            seq.save(update_fields=["last_value"])


def sync_supplier_purchase(item, user):
    """Keep a supplier 'purchase' ledger line in step with a purchased stock item."""
    txn = SupplierTransaction.objects.filter(stock_item=item, type=SupplierTransaction.Type.PURCHASE,
                                             is_voided=False).first()
    wants = bool(item.supplier_id) and item.source_type == StockItem.SourceType.CURRENT_PURCHASE
    old_supplier = txn.supplier if txn else None
    if wants:
        if txn:
            txn.supplier = item.supplier
            txn.amount = item.total_cost
            txn.gold_pasa = item.pasa
            txn.date = item.purchase_date or txn.date
            txn.save()
        else:
            SupplierTransaction.objects.create(
                supplier=item.supplier, date=item.purchase_date or timezone.localdate(),
                type=SupplierTransaction.Type.PURCHASE, amount=item.total_cost, gold_pasa=item.pasa,
                stock_item=item, notes=f"Item {item.code}", created_by=user,
            )
        item.supplier.recompute_balance()
    elif txn:
        txn.is_voided = True
        txn.save(update_fields=["is_voided", "updated_at"])
    if old_supplier and old_supplier.pk != item.supplier_id:
        old_supplier.recompute_balance()


def return_to_supplier(item, user, notes=""):
    if item.status != StockItem.Status.IN_STOCK:
        raise BusinessRuleError("Only in-stock items can be returned.")
    if not item.supplier_id:
        raise BusinessRuleError("This item has no supplier to return it to.")
    item.status = StockItem.Status.RETURNED
    item.updated_by = user
    item.save()
    SupplierTransaction.objects.create(
        supplier=item.supplier, date=timezone.localdate(), type=SupplierTransaction.Type.RETURN,
        amount=item.total_cost, gold_pasa=item.pasa, stock_item=item,
        notes=notes or f"Returned item {item.code}", created_by=user,
    )
    item.supplier.recompute_balance()
    return item
