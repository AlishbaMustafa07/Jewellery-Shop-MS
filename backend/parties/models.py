from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum

from core.models import TimeStampedModel


def _sum(qs, field):
    return qs.aggregate(t=Sum(field))["t"] or Decimal("0")


class Customer(TimeStampedModel):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True, db_index=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                          help_text="Balance brought forward from the old books")
    # Denormalised; positive = customer owes the shop. Recomputed from the ledger inside each transaction.
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return f"{self.name} ({self.phone})" if self.phone else self.name

    def recompute_balance(self, save=True):
        from sales.models import OldGoldIntake, Payment, Invoice

        invoices = Invoice.objects.filter(customer=self).exclude(status=Invoice.Status.VOIDED)
        old_gold = OldGoldIntake.objects.filter(invoice__in=invoices)
        payments = Payment.objects.filter(customer=self, is_voided=False).exclude(method=Payment.Method.ADVANCE)
        self.balance = (self.opening_balance + _sum(invoices, "net_amount")
                        - _sum(old_gold, "value") - _sum(payments, "amount"))
        if save:
            Customer.objects.filter(pk=self.pk).update(balance=self.balance)
        return self.balance

    def advance_credit(self):
        """Unapplied advances = advances received - advances adjusted against invoices."""
        from sales.models import Payment

        base = Payment.objects.filter(customer=self, is_voided=False)
        received = _sum(base.filter(kind=Payment.Kind.ADVANCE), "amount")
        applied = _sum(base.filter(method=Payment.Method.ADVANCE), "amount")
        return received - applied


class Supplier(TimeStampedModel):
    class Type(models.TextChoices):
        SUPPLIER = "supplier", "Supplier"
        KARIGAR = "karigar", "Karigar"

    name = models.CharField(max_length=200)
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.SUPPLIER)
    phone = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    # Denormalised; positive = shop owes the supplier.
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return self.name

    def recompute_balance(self, save=True):
        txns = self.transactions.filter(is_voided=False)
        plus = _sum(txns.filter(type__in=SupplierTransaction.CREDIT_TYPES), "amount")
        minus = _sum(txns.exclude(type__in=SupplierTransaction.CREDIT_TYPES), "amount")
        self.balance = self.opening_balance + plus - minus
        if save:
            Supplier.objects.filter(pk=self.pk).update(balance=self.balance)
        return self.balance


class SupplierTransaction(TimeStampedModel):
    """Ledger for suppliers/karigars. purchase/labour/adjustment raise what the shop owes;
    payment/return lower it."""

    class Type(models.TextChoices):
        PURCHASE = "purchase", "Purchase"
        LABOUR = "labour", "Karigar labour"
        ADJUSTMENT = "adjustment", "Adjustment (+)"
        PAYMENT = "payment", "Payment"
        RETURN = "return", "Return"

    CREDIT_TYPES = (Type.PURCHASE, Type.LABOUR, Type.ADJUSTMENT)

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="transactions")
    date = models.DateField()
    type = models.CharField(max_length=12, choices=Type.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    gold_pasa = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True,
                                    help_text="Gold given/received instead of cash (optional)")
    stock_item = models.ForeignKey("stock.StockItem", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="supplier_transactions")
    method = models.CharField(max_length=10, blank=True)
    cash_account = models.CharField(max_length=50, blank=True)
    cash_book_entry = models.ForeignKey("cashbook.CashBookEntry", null=True, blank=True, on_delete=models.SET_NULL,
                                        related_name="+")
    notes = models.TextField(blank=True)
    is_voided = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["date", "created_at"]

    def __str__(self):
        return f"{self.supplier.name} {self.get_type_display()} {self.amount}"
