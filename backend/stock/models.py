from django.conf import settings
from django.db import models

from core import calculations as calc
from core.models import TimeStampedModel


class StockItem(TimeStampedModel):
    class Metal(models.TextChoices):
        GOLD = "gold", "Gold"
        SILVER = "silver", "Silver"
        PALLADIUM = "palladium", "Palladium"

    class ItemType(models.TextChoices):
        PLAIN = "plain", "Plain"
        JURAO = "jurao", "Jurao"

    class Nature(models.TextChoices):
        NEW = "new", "New"
        TRANSFER = "transfer", "Transfer"
        KARIGAR = "karigar", "Karigar"
        OLD = "old", "Old"

    class SourceType(models.TextChoices):
        OPENING_STOCK = "opening_stock", "Opening stock"
        CURRENT_PURCHASE = "current_purchase", "Current purchase"

    class Status(models.TextChoices):
        IN_STOCK = "in_stock", "In stock"
        SOLD = "sold", "Sold"
        SR_REFINE = "sr_refine", "Sent to refine"
        RETURNED = "returned", "Returned"
        TRANSFERRED = "transferred", "Transferred"

    code = models.CharField(max_length=20, unique=True)
    metal = models.CharField(max_length=10, choices=Metal.choices, default=Metal.GOLD)
    category = models.CharField(max_length=50)
    name = models.CharField(max_length=200, blank=True)
    pieces = models.PositiveIntegerField(default=1)
    type = models.CharField(max_length=10, choices=ItemType.choices, default=ItemType.PLAIN)
    size = models.CharField(max_length=30, blank=True)
    design = models.CharField(max_length=100, blank=True)
    supplier = models.ForeignKey("parties.Supplier", null=True, blank=True, on_delete=models.PROTECT,
                                 related_name="items")
    nature = models.CharField(max_length=10, choices=Nature.choices, default=Nature.NEW)
    source_type = models.CharField(max_length=20, choices=SourceType.choices, default=SourceType.CURRENT_PURCHASE)
    book_no = models.CharField(max_length=30, blank=True)
    page_no = models.CharField(max_length=20, blank=True)

    gross_weight = models.DecimalField(max_digits=10, decimal_places=3)
    big_stone_weight = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    pd_diamond_weight = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    extra_less_gold = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    gold_weight = models.DecimalField(max_digits=10, decimal_places=3, default=0, editable=False)
    ratti_kaat = models.DecimalField(max_digits=5, decimal_places=2, default=90)
    pasa = models.DecimalField(max_digits=12, decimal_places=4, default=0, editable=False)
    purchase_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gold_price = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    extra_costs = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                      help_text="Beads, dropper, stones, diamond, silver")
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IN_STOCK)
    photo = models.ImageField(upload_to="stock/%Y/%m/", max_length=500, blank=True, null=True)
    purchase_date = models.DateField(null=True, blank=True)
    sold_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["category"]),
            models.Index(fields=["metal"]),
            models.Index(fields=["purchase_date"]),
            models.Index(fields=["status", "metal", "category"]),
        ]

    def __str__(self):
        return f"{self.code} {self.category} {self.gross_weight}g"

    def recalculate(self):
        values = calc.compute_stock_values(
            self.gross_weight, self.big_stone_weight, self.pd_diamond_weight, self.extra_less_gold,
            self.ratti_kaat, self.purchase_rate, self.extra_costs,
        )
        for k, v in values.items():
            setattr(self, k, v)

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        self.recalculate()
        super().save(*args, **kwargs)
