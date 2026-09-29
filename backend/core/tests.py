from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core import barcode
from core import calculations as calc
from core.models import AuditLog, GoldRate, User


class CalculationTests(TestCase):
    def test_spec_example_bin0001(self):
        # Spec section 5: 2.87 g x 90/96 = 2.6906 pasa -> x 43,600 / 11.664 ~ Rs 10,058
        self.assertEqual(calc.pasa(Decimal("2.87"), 90), Decimal("2.6906"))
        self.assertEqual(calc.gold_price(Decimal("2.87"), 90, 43600), Decimal("10058.00"))

    def test_gold_weight(self):
        self.assertEqual(calc.gold_weight("10.5", "0.75", "0.25", "-0.1"), Decimal("9.400"))
        self.assertEqual(calc.gold_weight("10", 0, 0, "0.2"), Decimal("10.200"))

    def test_making_modes(self):
        self.assertEqual(calc.making_charges("per_gram", 1000, Decimal("5"), 0), Decimal("5000.00"))
        self.assertEqual(calc.making_charges("per_tola", 11664, Decimal("11.664"), 0), Decimal("11664.00"))
        self.assertEqual(calc.making_charges("percent", 10, 0, Decimal("200000")), Decimal("20000.00"))
        self.assertEqual(calc.making_charges("fixed", "2500.4", 0, 0), Decimal("2500.00"))

    def test_money_rounds_to_rupee(self):
        self.assertEqual(calc.q_money("10.5"), Decimal("11.00"))
        self.assertEqual(calc.q_money("10.49"), Decimal("10.00"))


class BarcodeTests(TestCase):
    def test_patterns_are_valid(self):
        self.assertEqual(len(barcode.PATTERNS), 107)
        for p in barcode.PATTERNS[:-1]:
            self.assertEqual(sum(int(c) for c in p), 11)
        self.assertEqual(sum(int(c) for c in barcode.PATTERNS[-1]), 13)

    def test_checksum(self):
        # "R0111": start B(104) + chars; checksum known-by-construction
        values = barcode.encode("R0111")
        self.assertEqual(values[0], 104)
        self.assertEqual(values[-1], 106)
        data = values[1:-2]
        self.assertEqual(values[-2], (104 + sum(i * v for i, v in enumerate(data, 1))) % 103)
        self.assertIn("<svg", barcode.svg("R0111"))


class AuthAndRatesTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("boss", password="Str0ng!pass", role="owner")
        self.sales = User.objects.create_user("counter", password="Str0ng!pass", role="salesperson")
        self.client = APIClient()

    def test_login_returns_tokens_and_permissions(self):
        r = self.client.post("/api/v1/auth/login/", {"username": "counter", "password": "Str0ng!pass"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)
        self.assertFalse(r.data["user"]["permissions"]["view_profit"])
        self.assertTrue(AuditLog.objects.filter(action="login").exists())

    def test_error_format(self):
        r = self.client.post("/api/v1/auth/login/", {"username": "x", "password": "y"}, format="json")
        self.assertEqual(r.status_code, 401)
        self.assertIn("detail", r.data)
        self.assertIn("errors", r.data)

    def test_only_owner_manager_set_rate_and_past_rates_locked(self):
        today = timezone.localdate()
        self.client.force_authenticate(self.sales)
        r = self.client.post("/api/v1/gold-rates/", {"date": today, "buy_rate_per_tola": 1, "sell_rate_per_tola": 2})
        self.assertEqual(r.status_code, 403)
        self.client.force_authenticate(self.owner)
        r = self.client.post("/api/v1/gold-rates/", {"date": today, "buy_rate_per_tola": 400000,
                                                     "sell_rate_per_tola": 405000})
        self.assertEqual(r.status_code, 201)
        # today's rate can be corrected
        r = self.client.post("/api/v1/gold-rates/", {"date": today, "buy_rate_per_tola": 401000,
                                                     "sell_rate_per_tola": 406000})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(GoldRate.objects.get(date=today).sell_rate_per_tola, Decimal("406000"))
        # past rates cannot
        past = today - timezone.timedelta(days=3)
        GoldRate.objects.create(date=past, buy_rate_per_tola=1, sell_rate_per_tola=2)
        r = self.client.post("/api/v1/gold-rates/", {"date": past, "buy_rate_per_tola": 5, "sell_rate_per_tola": 6})
        self.assertEqual(r.status_code, 400)
        r = self.client.get("/api/v1/gold-rates/today/")
        self.assertTrue(r.data["is_today"])

    def test_audit_log_is_immutable(self):
        entry = AuditLog.objects.create(entity_type="x", entity_id="1", action="other")
        entry.note = "tamper"
        with self.assertRaises(Exception):
            entry.save()
        with self.assertRaises(Exception):
            entry.delete()

    def test_users_owner_only(self):
        self.client.force_authenticate(self.sales)
        self.assertEqual(self.client.get("/api/v1/users/").status_code, 403)
        self.client.force_authenticate(self.owner)
        r = self.client.post("/api/v1/users/", {"username": "new", "password": "An0ther!pass", "role": "manager"})
        self.assertEqual(r.status_code, 201, r.data)
