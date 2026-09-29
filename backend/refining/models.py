from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class RefineLot(TimeStampedModel):
    class Status(models.TextChoices):
        SENT = "sent", "At refiner"
        RETURNED = "returned", "Returned"

    date = models.DateField()
    refiner = models.CharField(max_length=100, help_text="e.g. MH Lab")
    weight_sent = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    expected_pasa = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    pasa_returned = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    returned_date = models.DateField(null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_cash_account = models.CharField(max_length=50, blank=True)
    cash_book_entry = models.ForeignKey("cashbook.CashBookEntry", null=True, blank=True, on_delete=models.SET_NULL,
                                        related_name="+")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SENT)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"Refine {self.date} {self.refiner} {self.weight_sent}g"

    @property
    def loss_pasa(self):
        if self.pasa_returned is None:
            return None
        return self.expected_pasa - self.pasa_returned


class RefineLotItem(models.Model):
    lot = models.ForeignKey(RefineLot, on_delete=models.CASCADE, related_name="items")
    stock_item = models.ForeignKey("stock.StockItem", null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="refine_items")
    old_gold_intake = models.ForeignKey("sales.OldGoldIntake", null=True, blank=True, on_delete=models.PROTECT,
                                        related_name="refine_items")
    weight = models.DecimalField(max_digits=10, decimal_places=3)
    pasa = models.DecimalField(max_digits=12, decimal_places=4)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(stock_item__isnull=False, old_gold_intake__isnull=True)
                | models.Q(stock_item__isnull=True, old_gold_intake__isnull=False),
                name="refine_item_exactly_one_source",
            )
        ]
