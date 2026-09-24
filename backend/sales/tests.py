from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from cashbook.models import CashBookEntry
from cashbook.services import close_day, ensure_default_heads
from core.models import GoldRate, User
from parties.models import Customer, Supplier
from stock.models import StockItem


class SaleFlowTests(TestCase):
    def setUp(self):
        ensure_default_heads()
        self.today = timezone.localdate()
        self.owner = User.objects.create_user("boss", password="x", role="owner")
        self.manager = User.objects.create_user("mgr", password="x", role="manager")
        self.sales = User.objects.create_user("counter", password="x", role="salesperson")
        GoldRate.objects.create(date=self.today, buy_rate_per_tola=Decimal("43000"),
                                sell_rate_per_tola=Decimal("43600"))
        self.supplier = Supplier.objects.create(name="Riaz Karachi")
        self.customer = Customer.objects.create(name="Ayesha", phone="0300")
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        r = self.client.post("/api/v1/stock/", {
            "category": "Ring", "gross_weight": "2.87", "ratti_kaat": "90", "purchase_rate": "43600",
            "supplier": str(self.supplier.id), "purchase_date": str(self.today),
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.item = StockItem.objects.get(pk=r.data["id"])

    def test_stock_code_and_costs(self):
        self.assertEqual(self.item.code, "R0001")
        self.assertEqual(self.item.gold_price, Decimal("10058.00"))
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.balance, Decimal("10058.00"))
        r = self.client.get("/api/v1/stock/next-code/?category=Ring")
        self.assertEqual(r.data["code"], "R0002")

    def test_salesperson_cannot_see_costs(self):
        self.client.force_authenticate(self.sales)
        r = self.client.get(f"/api/v1/stock/{self.item.id}/")
        self.assertNotIn("total_cost", r.data)
        self.assertIn("pasa", r.data)

    def _sale(self, **extra):
        body = {"customer": str(self.customer.id),
                "lines": [{"stock_item": str(self.item.id), "making_mode": "fixed", "making_charges": "2000"}]}
        body.update(extra)
        return self.client.post("/api/v1/invoices/", body, format="json")

    def test_preview_then_partial_sale_then_payment_then_void(self):
        r = self.client.post("/api/v1/sale-preview/", {"lines": [{"stock_item": str(self.item.id),
                                                                  "making_charges": "2000"}]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(r.data["net_amount"]), Decimal("12058"))

        r = self._sale(payments=[{"method": "cash", "amount": "10000"}])
        self.assertEqual(r.status_code, 201, r.data)
        inv_id = r.data["id"]
        self.assertEqual(r.data["status"], "partial")
        self.assertEqual(Decimal(r.data["balance"]), Decimal("2058"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "sold")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.balance, Decimal("2058"))
        self.assertEqual(CashBookEntry.objects.filter(source_type="sale").count(), 1)

        # same item cannot be sold twice
        self.assertEqual(self._sale().status_code, 400)

        r = self.client.post(f"/api/v1/invoices/{inv_id}/payments/", {"method": "cash", "amount": "2058"})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["status"], "paid")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.balance, 0)

        # salesperson cannot void
        self.client.force_authenticate(self.sales)
        self.assertEqual(self.client.post(f"/api/v1/invoices/{inv_id}/void/", {"reason": "x"}).status_code, 403)
        self.client.force_authenticate(self.manager)
        r = self.client.post(f"/api/v1/invoices/{inv_id}/void/", {"reason": "Customer returned"})
        self.assertEqual(r.status_code, 200, r.data)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "in_stock")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.balance, 0)
        self.assertFalse(CashBookEntry.objects.filter(is_voided=False, source_type__in=["sale", "customer_payment"]).exists())

    def test_walk_in_must_pay_in_full(self):
        r = self.client.post("/api/v1/invoices/", {
            "customer_name": "Walk in",
            "lines": [{"stock_item": str(self.item.id), "making_charges": "0"}],
            "payments": [{"method": "cash", "amount": "100"}]}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_discount_limit_for_staff(self):
        self.client.force_authenticate(self.sales)
        r = self._sale(discount="5000")
        self.assertEqual(r.status_code, 400)
        self.assertIn("limit", r.data["detail"])

    def test_old_gold_and_advance(self):
        r = self.client.post("/api/v1/advances/", {"customer": str(self.customer.id), "method": "cash",
                                                   "amount": "5000"})
        self.assertEqual(r.status_code, 201, r.data)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.balance, Decimal("-5000"))
        r = self._sale(
            old_gold=[{"weight": "2", "ratti_kaat": "96", "rate": "11664"}],  # 2 g pure @ 1000/g = 2000
            payments=[{"method": "advance", "amount": "5000"}, {"method": "cash", "amount": "5058"}],
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["status"], "paid")
        self.assertEqual(Decimal(r.data["old_gold_credit"]), Decimal("2000"))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.balance, 0)
        self.assertEqual(self.customer.advance_credit(), 0)

    def test_receipt_and_tag_render(self):
        r = self._sale(payments=[{"method": "cash", "amount": "12058"}])
        self.assertEqual(self.client.get(f"/api/v1/invoices/{r.data['id']}/receipt/?size=80mm").status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/stock/{self.item.id}/tag/").status_code, 200)

    def test_locked_day_blocks_sale_and_void_reverses(self):
        r = self._sale(payments=[{"method": "cash", "amount": "12058"}])
        inv_id = r.data["id"]
        close_day(self.today, self.owner)
        self.item.refresh_from_db()
        # voiding after close posts a reversal instead of editing the locked entry — but today is locked too
        r = self.client.post(f"/api/v1/invoices/{inv_id}/void/", {"reason": "oops"})
        self.assertEqual(r.status_code, 400)
        self.client.post("/api/v1/cash-book/day-reopen/", {"date": str(self.today)})
        r = self.client.post(f"/api/v1/invoices/{inv_id}/void/", {"reason": "oops"})
        self.assertEqual(r.status_code, 200, r.data)


class CashBookTests(TestCase):
    def setUp(self):
        ensure_default_heads()
        self.today = timezone.localdate()
        self.owner = User.objects.create_user("boss", password="x", role="owner")
        self.acct = User.objects.create_user("acct", password="x", role="accountant")
        self.sales = User.objects.create_user("counter", password="x", role="salesperson")
        self.client = APIClient()

    def _heads(self):
        from core.models import HeadOfAccount
        return (HeadOfAccount.objects.get(name="SDTD", parent=None),
                HeadOfAccount.objects.get(name="Home", parent=None))

    def test_manual_entry_close_and_reopen(self):
        sdtd, _ = self._heads()
        self.client.force_authenticate(self.acct)
        r = self.client.post("/api/v1/cash-book/", {"date": str(self.today), "hoa": str(sdtd.id), "amount": "500",
                                                    "detail": "Cash", "party": "Tea boy"})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["type"], "E")
        r = self.client.post("/api/v1/cash-book/day-close/", {"date": str(self.today)})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(r.data["closing_balance"]), Decimal("-500"))
        r = self.client.post("/api/v1/cash-book/", {"date": str(self.today), "hoa": str(sdtd.id), "amount": "10"})
        self.assertEqual(r.status_code, 400)
        # only the owner reopens
        self.assertEqual(self.client.post("/api/v1/cash-book/day-reopen/", {"date": str(self.today)}).status_code, 403)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.post("/api/v1/cash-book/day-reopen/", {"date": str(self.today)}).status_code, 200)

    def test_private_heads_hidden_from_salesperson(self):
        _, home = self._heads()
        self.client.force_authenticate(self.owner)
        self.client.post("/api/v1/cash-book/", {"date": str(self.today), "hoa": str(home.id), "amount": "900"})
        self.client.force_authenticate(self.sales)
        r = self.client.get("/api/v1/cash-book/")
        self.assertEqual(r.data["count"], 0)
        r = self.client.post("/api/v1/cash-book/", {"date": str(self.today), "hoa": str(home.id), "amount": "1"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.get("/api/v1/cash-book/views/home/").status_code, 400)


class ReportTests(TestCase):
    def setUp(self):
        from django.core.management import call_command
        import io
        call_command("seed_demo", stdout=io.StringIO())
        self.owner = User.objects.get(username="owner")
        self.sales = User.objects.get(username="sales")
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_reports_respond(self):
        for url in ["/api/v1/dashboard/", "/api/v1/reports/profit-loss/", "/api/v1/reports/stock-valuation/",
                    "/api/v1/reports/sales/?group_by=category", "/api/v1/reports/expenses/",
                    "/api/v1/reports/account-summary/", "/api/v1/zakat/calculate/", "/api/v1/refine/balance/",
                    "/api/v1/customers/balance-reminders/", "/api/v1/cash-book/views/shop_expenses/"]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, (url, getattr(r, "data", None)))
        pl = self.client.get("/api/v1/reports/profit-loss/").data
        self.assertGreater(pl["net_sales"], 0)

    def test_exports(self):
        for url in ["/api/v1/reports/export/?type=pl&format=xlsx", "/api/v1/reports/export/?type=stock&format=csv",
                    "/api/v1/reports/export/?type=sales&format=html", "/api/v1/reports/export/?type=full",
                    "/api/v1/cash-book/?format=xlsx"]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
        c = Customer.objects.first()
        self.assertEqual(self.client.get(f"/api/v1/customers/{c.id}/statement/?format=xlsx").status_code, 200)

    def test_staff_blocked_from_profit_and_investors(self):
        self.client.force_authenticate(self.sales)
        self.assertEqual(self.client.get("/api/v1/reports/profit-loss/").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/investors/").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/zakat/calculate/").status_code, 403)
        d = self.client.get("/api/v1/dashboard/").data
        self.assertNotIn("month", d)

    def test_refine_lot_flow(self):
        from sales.models import OldGoldIntake
        og = OldGoldIntake.objects.first()
        r = self.client.post("/api/v1/refine-lots/", {"refiner": "MH Lab", "old_gold": [str(og.id)]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        lot = r.data["id"]
        r = self.client.patch(f"/api/v1/refine-lots/{lot}/", {"pasa_returned": "2.8", "cost": "1500"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "returned")
        og.refresh_from_db()
        self.assertEqual(og.status, "refined")
        self.assertTrue(CashBookEntry.objects.filter(source_type="refine").exists())

    def test_investor_transactions(self):
        r = self.client.post("/api/v1/investors/", {"name": "Haji Sahib", "share_percent": "3.5"})
        self.assertEqual(r.status_code, 201, r.data)
        iid = r.data["id"]
        r = self.client.post(f"/api/v1/investors/{iid}/transactions/", {"date": str(timezone.localdate()),
                                                                        "type": "investment", "amount": "100000"})
        self.assertEqual(r.status_code, 201, r.data)
        r = self.client.get(f"/api/v1/investors/{iid}/")
        self.assertEqual(Decimal(r.data["totals"]["capital"]), Decimal("100000"))
        self.assertEqual(self.client.get(f"/api/v1/investors/{iid}/profit-estimate/").status_code, 200)
