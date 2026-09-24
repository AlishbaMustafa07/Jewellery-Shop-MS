"""Demo data so the system can be tried end-to-end. Never run on the live database."""
import datetime
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from cashbook.models import CashBookEntry
from cashbook.services import ensure_default_heads
from core.models import GoldRate, HeadOfAccount, User
from parties.models import Customer, Supplier
from sales import services as sales
from stock import services as stock_services
from stock.models import StockItem

USERS = [
    ("owner", "owner", "Owner"),
    ("manager", "manager", "Manager"),
    ("accountant", "accountant", "Accountant"),
    ("sales", "salesperson", "Counter"),
]
DEMO_PASSWORD = "alnoor@2026"


class Command(BaseCommand):
    help = "Load demo users, rates, suppliers, customers, stock, sales and cash-book entries."

    @transaction.atomic
    def handle(self, *args, **opts):
        random.seed(7)
        ensure_default_heads()
        users = {}
        for username, role, first in USERS:
            u, _ = User.objects.get_or_create(username=username, defaults={"first_name": first, "role": role})
            u.role = role
            u.is_staff = role == "owner"
            u.is_superuser = role == "owner"
            u.set_password(DEMO_PASSWORD)
            u.save()
            users[role] = u
        owner = users["owner"]

        today = timezone.localdate()
        for i in range(30, -1, -1):
            d = today - datetime.timedelta(days=i)
            base = Decimal(430000 + (30 - i) * 350)
            GoldRate.objects.get_or_create(date=d, defaults={
                "buy_rate_per_tola": base - 3000, "sell_rate_per_tola": base, "entered_by": owner})

        suppliers = [Supplier.objects.get_or_create(name=n, defaults={"type": t})[0] for n, t in [
            ("Riaz Karachi", "supplier"), ("Saeen Jewellers", "supplier"), ("Ustad Akram", "karigar")]]
        customers = [Customer.objects.get_or_create(name=n, defaults={"phone": p})[0] for n, p in [
            ("Ayesha Khan", "03001234567"), ("Bilal Ahmed", "03211112222"), ("Fatima Noor", "03335556666"),
            ("Hamza Ali", "03124445555")]]

        cats = ["Ring", "Earrings", "Locket Set", "Necklace Set", "Bangles", "Chain"]
        weights = {"Ring": (2.5, 6), "Earrings": (3, 8), "Locket Set": (8, 16), "Necklace Set": (20, 45),
                   "Bangles": (15, 35), "Chain": (5, 15)}
        if StockItem.objects.count() < 10:
            for n in range(36):
                cat = cats[n % len(cats)]
                lo, hi = weights[cat]
                gross = Decimal(str(round(random.uniform(lo, hi), 3)))
                pdate = today - datetime.timedelta(days=random.randint(0, 400))
                rate = GoldRate.for_date(pdate) or GoldRate.objects.order_by("date").first()
                item = StockItem.objects.create(
                    code=stock_services.next_code(cat), metal="gold", category=cat, name=f"{cat} design {n + 1}",
                    design=f"D-{100 + n}", supplier=random.choice(suppliers[:2]),
                    gross_weight=gross, big_stone_weight=Decimal("0.2") if cat == "Necklace Set" else 0,
                    ratti_kaat=random.choice([Decimal(88), Decimal(90), Decimal(92)]),
                    purchase_rate=rate.buy_rate_per_tola, extra_costs=Decimal(random.choice([0, 0, 1500, 4000])),
                    purchase_date=pdate, created_by=owner, updated_by=owner,
                )
                stock_services.sync_supplier_purchase(item, owner)
            for n in range(6):
                StockItem.objects.create(
                    code=f"S{n + 1:04d}", metal="silver", category="Bracelet" if n % 2 else "Ring",
                    name="Silver piece", gross_weight=Decimal("12.5") + n, ratti_kaat=Decimal(96),
                    purchase_rate=0, extra_costs=Decimal(2500 + n * 300), purchase_date=today, created_by=owner,
                )

            items = list(StockItem.objects.filter(metal="gold", status="in_stock")[:5])
            sales.create_invoice({
                "customer": customers[0],
                "lines": [{"stock_item": items[0], "making_mode": "per_gram", "making_rate": Decimal(1500)},
                          {"stock_item": items[1], "making_charges": Decimal(8000)}],
                "discount": Decimal(1000),
                "payments": [{"method": "cash", "amount": Decimal(200000)}],
                "old_gold": [{"description": "Old ring", "weight": Decimal("3.2"), "ratti_kaat": Decimal(86)}],
            }, owner)
            walk_in_lines = [{"stock_item": items[2], "making_charges": Decimal(5000)}]
            net = sales.preview({"lines": walk_in_lines})["net_amount"]
            sales.create_invoice({"customer_name": "Walk-in", "lines": walk_in_lines,
                                  "payments": [{"method": "card", "amount": net}]}, owner)
            sales.create_advance(customers[2], {"method": "cash", "amount": Decimal(50000)}, owner)

            sdtd = HeadOfAccount.objects.get(name="SDTD", parent=None)
            for sub, amt in [("Tea", 800), ("Electricity", 18500), ("Salary", 45000)]:
                CashBookEntry.objects.create(
                    date=today, type="E", hoa=sdtd, sub_hoa=HeadOfAccount.objects.get(name=sub, parent=sdtd),
                    amount=Decimal(amt), detail="Cash", debited_to="Shop", party=sub, created_by=owner,
                )
            opening = HeadOfAccount.objects.get(name="Investment", parent=None)
            CashBookEntry.objects.create(date=today - datetime.timedelta(days=31), type="I", hoa=opening,
                                         amount=Decimal(2500000), detail="Opening cash", party="Owner",
                                         created_by=owner)

        self.stdout.write(self.style.SUCCESS(
            f"Demo data loaded. Log in as owner / manager / accountant / sales with password '{DEMO_PASSWORD}'."))
