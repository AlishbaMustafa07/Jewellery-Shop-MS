from django.conf import settings
from django.db import models

from core.models import HeadOfAccount, TimeStampedModel


class CashBookEntry(TimeStampedModel):
    class Type(models.TextChoices):
        INCOME = "I", "Income"
        EXPENDITURE = "E", "Expenditure"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        SALE = "sale", "Sale"
        ADVANCE = "advance", "Advance"
        CUSTOMER_PAYMENT = "customer_payment", "Customer payment"
        SUPPLIER_PAYMENT = "supplier_payment", "Supplier payment"
        REFINE = "refine", "Refine"
        INVESTOR = "investor", "Investor"
        REVERSAL = "reversal", "Reversal"
        IMPORT = "import", "Import"

    date = models.DateField(db_index=True)
    type = models.CharField(max_length=1, choices=Type.choices, db_index=True)
    hoa = models.ForeignKey(HeadOfAccount, on_delete=models.PROTECT, related_name="entries")
    sub_hoa = models.ForeignKey(HeadOfAccount, null=True, blank=True, on_delete=models.PROTECT,
                                related_name="sub_entries")
    detail = models.CharField(max_length=100, blank=True, help_text="Cash / MBI / Salami ...")
    debited_to = models.CharField(max_length=100, blank=True, help_text="Shop / Home / Refine / person")
    party = models.CharField(max_length=200, blank=True, help_text="Received from / Paid to")
    book_no = models.CharField(max_length=30, blank=True)
    page_no = models.CharField(max_length=20, blank=True)
    pound_weight = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    pasa_weight = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    rate = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    source_type = models.CharField(max_length=30, choices=Source.choices, default=Source.MANUAL)
    source_id = models.UUIDField(null=True, blank=True)
    cash_account = models.CharField(max_length=50, default="shop_cash", db_index=True)
    notes = models.TextField(blank=True)
    is_voided = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=200, blank=True)
    day_locked = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name_plural = "cash book entries"
        indexes = [
            models.Index(fields=["hoa"]),
            models.Index(fields=["source_type", "source_id"]),
        ]

    def __str__(self):
        return f"{self.date} {self.type} {self.hoa.name} {self.amount}"

    @property
    def signed_amount(self):
        return self.amount if self.type == self.Type.INCOME else -self.amount


class DayClose(models.Model):
    date = models.DateField(primary_key=True)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2)
    total_income = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_expenditure = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=14, decimal_places=2)
    breakdown = models.JSONField(default=dict, blank=True, help_text="Per cash-account opening/in/out/closing")
    counted_cash = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                       help_text="Physical cash counted at close (optional)")
    notes = models.TextField(blank=True)
    is_locked = models.BooleanField(default=True)
    locked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    locked_at = models.DateTimeField(null=True)
    reopened_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    reopened_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Day close {self.date}"
