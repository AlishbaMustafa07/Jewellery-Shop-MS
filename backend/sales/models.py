from django.conf import settings
from django.db import models

from core.calculations import MakingMode
from core.models import TimeStampedModel


class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PARTIAL = "partial", "Partial"
        PAID = "paid", "Paid"
        VOIDED = "voided", "Voided"

    number = models.CharField(max_length=30, unique=True)
    date = models.DateField(db_index=True)
    customer = models.ForeignKey("parties.Customer", null=True, blank=True, on_delete=models.PROTECT,
                                 related_name="invoices")
    customer_name = models.CharField(max_length=200, blank=True, help_text="Walk-in customer name")
    customer_phone = models.CharField(max_length=20, blank=True)
    legacy_book = models.CharField(max_length=30, blank=True)
    legacy_page = models.CharField(max_length=20, blank=True)
    sale_rate = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    old_gold_credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    salesperson = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                    related_name="invoices")
    notes = models.TextField(blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=300, blank=True)
    voided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="+")

    class Meta:
        ordering = ["-date", "-number"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["customer"])]

    def __str__(self):
        return self.number

    @property
    def display_customer(self):
        if self.customer_id:
            return self.customer.name
        return self.customer_name or "Walk-in"

    def refresh_totals(self, save=True):
        """paid = real payments + advance adjustments + old gold credit."""
        from django.db.models import Sum

        paid = self.payments.filter(is_voided=False).aggregate(t=Sum("amount"))["t"] or 0
        self.paid_amount = paid + self.old_gold_credit
        self.balance = self.net_amount - self.paid_amount
        if self.status != self.Status.VOIDED:
            if self.balance <= 0:
                self.status = self.Status.PAID
            elif self.paid_amount > 0:
                self.status = self.Status.PARTIAL
            else:
                self.status = self.Status.OPEN
        if save:
            self.save(update_fields=["paid_amount", "balance", "status", "updated_at"])


class SaleLine(TimeStampedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    stock_item = models.ForeignKey("stock.StockItem", null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="sale_lines")
    description = models.CharField(max_length=200, blank=True)
    weight = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    ratti_kaat = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    pasa = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    gold_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    making_mode = models.CharField(max_length=10, choices=MakingMode.CHOICES, default=MakingMode.FIXED)
    making_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    making_charges = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stone_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    purchase_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.description or (self.stock_item.code if self.stock_item_id else "line")


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        BANK = "bank", "Bank"
        CARD = "card", "Card"
        ADVANCE = "advance", "Adjusted from advance"

    class Kind(models.TextChoices):
        SALE = "sale", "Sale payment"
        ADVANCE = "advance", "Advance"
        RECEIVABLE = "receivable", "Payment against balance"

    invoice = models.ForeignKey(Invoice, null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    customer = models.ForeignKey("parties.Customer", null=True, blank=True, on_delete=models.PROTECT,
                                 related_name="payments")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.SALE)
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.CASH)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField(db_index=True)
    cash_account = models.CharField(max_length=50, default="shop_cash")
    reference = models.CharField(max_length=100, blank=True, help_text="Bank/card reference")
    notes = models.TextField(blank=True)
    cash_book_entry = models.ForeignKey("cashbook.CashBookEntry", null=True, blank=True, on_delete=models.SET_NULL,
                                        related_name="+")
    is_voided = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.amount} ({self.method})"


class OldGoldIntake(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT_TO_REFINE = "sent_to_refine", "Sent to refine"
        REFINED = "refined", "Refined"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="old_gold")
    description = models.CharField(max_length=200, blank=True)
    weight = models.DecimalField(max_digits=10, decimal_places=3)
    ratti_kaat = models.DecimalField(max_digits=5, decimal_places=2)
    pasa = models.DecimalField(max_digits=12, decimal_places=4)
    rate = models.DecimalField(max_digits=12, decimal_places=2)
    deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                    help_text="Wastage/testing deduction in PKR")
    value = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Old gold {self.weight}g on {self.invoice.number}"
