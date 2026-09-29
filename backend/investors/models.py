from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum

from core.models import TimeStampedModel


class Investor(TimeStampedModel):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    book_no = models.CharField(max_length=30, blank=True)
    page_no = models.CharField(max_length=20, blank=True)
    share_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="e.g. 3.5")
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def totals(self):
        txns = self.transactions.filter(is_voided=False)

        def s(t):
            return txns.filter(type=t).aggregate(x=Sum("amount"))["x"] or Decimal("0")

        invested, withdrawn, profit = s("investment"), s("withdrawal"), s("profit_paid")
        return {"invested": invested, "withdrawn": withdrawn, "capital": invested - withdrawn, "profit_paid": profit}


class InvestorTransaction(TimeStampedModel):
    class Type(models.TextChoices):
        INVESTMENT = "investment", "Investment"
        WITHDRAWAL = "withdrawal", "Withdrawal"
        PROFIT_PAID = "profit_paid", "Profit paid"

    investor = models.ForeignKey(Investor, on_delete=models.PROTECT, related_name="transactions")
    date = models.DateField()
    type = models.CharField(max_length=12, choices=Type.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    cash_account = models.CharField(max_length=50, default="shop_cash")
    period_from = models.DateField(null=True, blank=True, help_text="Profit period (profit_paid only)")
    period_to = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    cash_book_entry = models.ForeignKey("cashbook.CashBookEntry", null=True, blank=True, on_delete=models.SET_NULL,
                                        related_name="+")
    is_voided = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.investor.name} {self.get_type_display()} {self.amount}"
