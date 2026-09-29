import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import PermissionDenied
from django.db import models, transaction


class TimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        ACCOUNTANT = "accountant", "Accountant"
        SALESPERSON = "salesperson", "Salesperson"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SALESPERSON)
    phone = models.CharField(max_length=20, blank=True)
    # Max discount (PKR) this user may give on one invoice; null = use the shop default for the role.
    discount_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.OWNER
        super().save(*args, **kwargs)

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER

    @property
    def can_view_profit(self):
        return self.role in (self.Role.OWNER, self.Role.MANAGER)

    @property
    def can_view_private(self):
        """Home / zakat / investor style entries are hidden from salespeople."""
        return self.role in (self.Role.OWNER, self.Role.MANAGER, self.Role.ACCOUNTANT)

    def effective_discount_limit(self):
        if self.role == self.Role.OWNER:
            return None  # unlimited
        if self.discount_limit is not None:
            return self.discount_limit
        shop = ShopSettings.load()
        if self.role == self.Role.MANAGER:
            return shop.default_discount_limit_manager
        return shop.default_discount_limit_staff


def default_code_prefixes():
    return {
        "Ring": "R",
        "Earrings": "E",
        "Locket Set": "LS",
        "Necklace Set": "NS",
        "Bangles": "BN",
        "Bracelet": "BR",
        "Chain": "CH",
        "Pendant": "P",
        "Nose Pin": "NP",
        "Tops": "T",
        "Kara": "K",
        "Misc": "M",
    }


def default_cash_accounts():
    return ["shop_cash", "MBI", "bank"]


class ShopSettings(models.Model):
    """Singleton row (pk=1) holding shop-wide configuration."""

    class SaleGoldBasis(models.TextChoices):
        PASA = "pasa", "Pasa (pure-gold equivalent)"
        WEIGHT = "weight", "Gold weight"

    shop_name = models.CharField(max_length=200, default="New Al-Noor Jewellers")
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    logo = models.ImageField(upload_to="logo/", blank=True, null=True)
    code_prefixes = models.JSONField(default=default_code_prefixes)
    cash_accounts = models.JSONField(default=default_cash_accounts)
    default_discount_limit_manager = models.DecimalField(max_digits=12, decimal_places=2, default=50000)
    default_discount_limit_staff = models.DecimalField(max_digits=12, decimal_places=2, default=2000)
    receipt_footer_text = models.TextField(
        default="Thank you for your purchase. Please keep this receipt for exchange or return."
    )
    invoice_prefix = models.CharField(max_length=10, default="INV")
    sale_gold_basis = models.CharField(max_length=10, choices=SaleGoldBasis.choices, default=SaleGoldBasis.PASA)
    zakat_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=2.5)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "shop settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.shop_name


class HeadOfAccount(models.Model):
    class Type(models.TextChoices):
        INCOME = "I", "Income"
        EXPENDITURE = "E", "Expenditure"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    type = models.CharField(max_length=1, choices=Type.choices)
    report_group = models.CharField(
        max_length=50, blank=True, help_text="shop_expenses | home | zakat | refine | oj | shopjew ..."
    )
    is_private = models.BooleanField(default=False, help_text="Hidden from salespeople (home, zakat, investors ...)")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["type", "name"]
        unique_together = [("name", "parent", "type")]

    def __str__(self):
        return f"{self.parent.name} > {self.name}" if self.parent_id else self.name


class GoldRate(models.Model):
    """One buy and one sell rate per day. Past rates are never overwritten."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True)
    buy_rate_per_tola = models.DecimalField(max_digits=12, decimal_places=2)
    sell_rate_per_tola = models.DecimalField(max_digits=12, decimal_places=2)
    entered_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date}: buy {self.buy_rate_per_tola} / sell {self.sell_rate_per_tola}"

    @classmethod
    def for_date(cls, date):
        """Latest rate on or before the given date."""
        return cls.objects.filter(date__lte=date).order_by("-date").first()


class Sequence(models.Model):
    """Counters (invoice numbers, stock codes) that are safe under concurrent use."""

    name = models.CharField(max_length=50, primary_key=True)
    last_value = models.PositiveIntegerField(default=0)

    @classmethod
    def next_value(cls, name, floor=0):
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(name=name)
            seq.last_value = max(seq.last_value, floor) + 1
            seq.save(update_fields=["last_value"])
            return seq.last_value

    @classmethod
    def peek(cls, name, floor=0):
        seq = cls.objects.filter(name=name).first()
        return max(seq.last_value if seq else 0, floor) + 1


class AuditLog(models.Model):
    """Immutable audit trail: who changed what, when, with old/new values."""

    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        VOID = "void", "Void"
        LOGIN = "login", "Login"
        LOCK = "lock", "Lock"
        UNLOCK = "unlock", "Unlock"
        OTHER = "other", "Other"

    id = models.BigAutoField(primary_key=True)
    entity_type = models.CharField(max_length=60)
    entity_id = models.CharField(max_length=64)
    entity_repr = models.CharField(max_length=200, blank=True)
    action = models.CharField(max_length=10, choices=Action.choices)
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    changes = models.JSONField(default=dict, blank=True)
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["user"]),
            models.Index(fields=["created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionDenied("Audit log entries are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("Audit log entries are immutable.")
