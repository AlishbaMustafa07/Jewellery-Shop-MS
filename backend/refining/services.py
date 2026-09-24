from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from cashbook import services as cashbook
from core import audit
from core import calculations as calc
from core.exceptions import BusinessRuleError
from core.models import GoldRate
from sales.models import Invoice, OldGoldIntake
from stock.models import StockItem

from .models import RefineLot, RefineLotItem

ZERO = Decimal("0")


def _attach(lot, stock_ids, old_gold_ids):
    items = list(StockItem.objects.select_for_update().filter(pk__in=stock_ids))
    if len(items) != len(set(stock_ids)):
        raise BusinessRuleError("Some stock items were not found.")
    for it in items:
        if it.status != StockItem.Status.IN_STOCK:
            raise BusinessRuleError(f"Item {it.code} is not in stock.")
        it.status = StockItem.Status.SR_REFINE
        it.save()
        RefineLotItem.objects.create(lot=lot, stock_item=it, weight=it.gold_weight, pasa=it.pasa)
    intakes = list(OldGoldIntake.objects.select_for_update().filter(pk__in=old_gold_ids)
                   .exclude(invoice__status=Invoice.Status.VOIDED))
    if len(intakes) != len(set(old_gold_ids)):
        raise BusinessRuleError("Some old-gold entries were not found.")
    for og in intakes:
        if og.status != OldGoldIntake.Status.PENDING:
            raise BusinessRuleError(f"Old gold on {og.invoice.number} has already gone to refine.")
        og.status = OldGoldIntake.Status.SENT_TO_REFINE
        og.save(update_fields=["status", "updated_at"])
        RefineLotItem.objects.create(lot=lot, old_gold_intake=og, weight=og.weight, pasa=og.pasa)


def _refresh_totals(lot, weight_override=None):
    agg = lot.items.aggregate(w=Sum("weight"), p=Sum("pasa"))
    lot.expected_pasa = agg["p"] or ZERO
    lot.weight_sent = weight_override if weight_override else (agg["w"] or ZERO)


@transaction.atomic
def create_lot(data, user):
    stock_ids = data.get("stock_items", [])
    og_ids = data.get("old_gold", [])
    if not stock_ids and not og_ids and not data.get("weight_sent"):
        raise BusinessRuleError("Add items, old gold, or a weight for the lot.")
    lot = RefineLot.objects.create(
        date=data.get("date") or timezone.localdate(), refiner=data["refiner"], notes=data.get("notes", ""),
        created_by=user,
    )
    _attach(lot, stock_ids, og_ids)
    _refresh_totals(lot, data.get("weight_sent"))
    if not lot.expected_pasa and data.get("expected_pasa"):
        lot.expected_pasa = data["expected_pasa"]
    lot.save()
    audit.log_create(user, lot)
    return lot


@transaction.atomic
def record_return(lot, data, user):
    lot = RefineLot.objects.select_for_update().get(pk=lot.pk)
    old = audit.snapshot(lot)
    if "pasa_returned" in data and data["pasa_returned"] is not None:
        lot.pasa_returned = data["pasa_returned"]
        lot.returned_date = data.get("returned_date") or timezone.localdate()
        lot.status = RefineLot.Status.RETURNED
        OldGoldIntake.objects.filter(refine_items__lot=lot).update(status=OldGoldIntake.Status.REFINED)
    for f in ("refiner", "notes"):
        if f in data:
            setattr(lot, f, data[f])
    new_cost = data.get("cost")
    if new_cost is not None and calc.D(new_cost) != lot.cost:
        if lot.cash_book_entry:
            cashbook.void_or_reverse(lot.cash_book_entry, user, "Refine cost changed")
            lot.cash_book_entry = None
        lot.cost = calc.q_money(new_cost)
        if lot.cost > 0:
            account = data.get("cost_cash_account") or "shop_cash"
            lot.cost_cash_account = account
            lot.cash_book_entry = cashbook.post_entry(
                key="refine", date=lot.returned_date or timezone.localdate(), amount=lot.cost, user=user,
                source_type="refine", source_id=lot.id, party=lot.refiner, detail="Refining charges",
                cash_account=account, debited_to="Refine",
            )
    lot.save()
    audit.log_update(user, lot, old)
    return lot


@transaction.atomic
def remove_item(lot, item_id, user):
    if lot.status == RefineLot.Status.RETURNED:
        raise BusinessRuleError("The lot has already come back from the refiner.")
    ri = lot.items.select_related("stock_item", "old_gold_intake").get(pk=item_id)
    if ri.stock_item:
        ri.stock_item.status = StockItem.Status.IN_STOCK
        ri.stock_item.save()
    if ri.old_gold_intake:
        ri.old_gold_intake.status = OldGoldIntake.Status.PENDING
        ri.old_gold_intake.save(update_fields=["status", "updated_at"])
    ri.delete()
    _refresh_totals(lot)
    lot.save()
    audit.log(user, "update", lot, note=f"Removed item {item_id} from lot")
    return lot


def refine_balance():
    """Current refine pool: gold waiting to go, gold at the refiner, and fine gold returned."""
    rate = GoldRate.objects.order_by("-date").first()
    buy = rate.buy_rate_per_tola if rate else None

    pending_og = OldGoldIntake.objects.filter(status=OldGoldIntake.Status.PENDING).exclude(
        invoice__status=Invoice.Status.VOIDED)
    og = pending_og.aggregate(w=Sum("weight"), p=Sum("pasa"), v=Sum("value"))
    at_refiner = RefineLot.objects.filter(status=RefineLot.Status.SENT).aggregate(
        w=Sum("weight_sent"), p=Sum("expected_pasa"), c=Sum("cost"))
    returned = RefineLot.objects.filter(status=RefineLot.Status.RETURNED).aggregate(
        exp=Sum("expected_pasa"), got=Sum("pasa_returned"), c=Sum("cost"))

    def val(p):
        return calc.value_of_pasa(p or 0, buy) if buy else None

    return {
        "rate_used": buy,
        "pending_old_gold": {"count": pending_og.count(), "weight": og["w"] or ZERO, "pasa": og["p"] or ZERO,
                             "credited_value": og["v"] or ZERO, "value_now": val(og["p"])},
        "at_refiner": {"weight": at_refiner["w"] or ZERO, "pasa": at_refiner["p"] or ZERO,
                       "value_now": val(at_refiner["p"])},
        "refined": {"expected_pasa": returned["exp"] or ZERO, "pasa_returned": returned["got"] or ZERO,
                    "loss_pasa": (returned["exp"] or ZERO) - (returned["got"] or ZERO),
                    "value_now": val(returned["got"]), "total_cost": returned["c"] or ZERO},
        "pool_pasa": (og["p"] or ZERO) + (at_refiner["p"] or ZERO) + (returned["got"] or ZERO),
    }
