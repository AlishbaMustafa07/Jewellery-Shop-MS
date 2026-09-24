from rest_framework import serializers

from core.calculations import MakingMode
from parties.models import Customer
from stock.models import StockItem

from .models import Invoice, OldGoldIntake, Payment, SaleLine

PROFIT_FIELDS = ("purchase_cost", "profit")


class ProfitHidingMixin:
    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request and not request.user.can_view_profit:
            for f in PROFIT_FIELDS:
                data.pop(f, None)
        return data


# ---------- input ----------

class LineInputSerializer(serializers.Serializer):
    stock_item = serializers.PrimaryKeyRelatedField(queryset=StockItem.objects.all(), required=False, allow_null=True)
    stock_code = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True, max_length=200)
    weight = serializers.DecimalField(max_digits=10, decimal_places=3, required=False, allow_null=True)
    ratti_kaat = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    pasa = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)
    gold_value = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    making_mode = serializers.ChoiceField(choices=MakingMode.CHOICES, required=False, default=MakingMode.FIXED)
    making_rate = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    making_charges = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    stone_value = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    purchase_cost = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)


class PaymentInputSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=Payment.Method.choices)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    cash_account = serializers.CharField(required=False, allow_blank=True)
    reference = serializers.CharField(required=False, allow_blank=True)
    date = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class OldGoldInputSerializer(serializers.Serializer):
    description = serializers.CharField(required=False, allow_blank=True)
    weight = serializers.DecimalField(max_digits=10, decimal_places=3)
    ratti_kaat = serializers.DecimalField(max_digits=5, decimal_places=2)
    rate = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    deduction = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)


class NewCustomerSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)


class InvoiceInputSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), required=False, allow_null=True)
    new_customer = NewCustomerSerializer(required=False)
    customer_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    customer_phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    sale_rate = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    discount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0, min_value=0)
    legacy_book = serializers.CharField(required=False, allow_blank=True)
    legacy_page = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    lines = LineInputSerializer(many=True)
    payments = PaymentInputSerializer(many=True, required=False, default=list)
    old_gold = OldGoldInputSerializer(many=True, required=False, default=list)


class VoidSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300)


# ---------- output ----------

class SaleLineSerializer(ProfitHidingMixin, serializers.ModelSerializer):
    stock_code = serializers.CharField(source="stock_item.code", read_only=True, default=None)
    category = serializers.CharField(source="stock_item.category", read_only=True, default=None)
    metal = serializers.CharField(source="stock_item.metal", read_only=True, default=None)

    class Meta:
        model = SaleLine
        exclude = ["invoice", "created_at", "updated_at"]


class PaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.number", read_only=True, default=None)
    customer_name = serializers.CharField(source="customer.name", read_only=True, default=None)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True, default=None)

    class Meta:
        model = Payment
        fields = ["id", "invoice", "invoice_number", "customer", "customer_name", "kind", "method", "amount", "date",
                  "cash_account", "reference", "notes", "is_voided", "created_by_name", "created_at"]


class OldGoldSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.number", read_only=True)
    customer_name = serializers.CharField(source="invoice.display_customer", read_only=True)
    date = serializers.DateField(source="invoice.date", read_only=True)

    class Meta:
        model = OldGoldIntake
        fields = ["id", "invoice", "invoice_number", "customer_name", "date", "description", "weight", "ratti_kaat",
                  "pasa", "rate", "deduction", "value", "status"]


class InvoiceListSerializer(serializers.ModelSerializer):
    customer_display = serializers.CharField(source="display_customer", read_only=True)
    salesperson_name = serializers.CharField(source="salesperson.username", read_only=True, default=None)
    line_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Invoice
        fields = ["id", "number", "date", "customer", "customer_display", "customer_phone", "sale_rate", "subtotal",
                  "discount", "net_amount", "old_gold_credit", "paid_amount", "balance", "status", "salesperson",
                  "salesperson_name", "legacy_book", "legacy_page", "line_count", "created_at"]


class InvoiceDetailSerializer(InvoiceListSerializer):
    lines = SaleLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    old_gold = OldGoldSerializer(many=True, read_only=True)
    voided_by_name = serializers.CharField(source="voided_by.username", read_only=True, default=None)
    profit = serializers.SerializerMethodField()

    class Meta(InvoiceListSerializer.Meta):
        fields = InvoiceListSerializer.Meta.fields + [
            "notes", "lines", "payments", "old_gold", "voided_at", "void_reason", "voided_by_name", "profit",
        ]

    def get_profit(self, obj):
        request = self.context.get("request")
        if request and not request.user.can_view_profit:
            return None
        return str(sum((l.profit for l in obj.lines.all()), 0) - obj.discount)


def preview_to_json(p, can_view_profit):
    def line(l):
        out = {k: (str(v) if v is not None and not hasattr(v, "pk") else v) for k, v in l.items() if k != "stock_item"}
        item = l["stock_item"]
        out["stock_item"] = str(item.pk) if item else None
        out["stock_code"] = item.code if item else None
        if not can_view_profit:
            for f in PROFIT_FIELDS:
                out.pop(f, None)
        return out

    data = {k: str(v) for k, v in p.items() if k not in ("lines", "old_gold")}
    data["lines"] = [line(l) for l in p["lines"]]
    data["old_gold"] = [{k: str(v) for k, v in o.items()} for o in p["old_gold"]]
    if not can_view_profit:
        data.pop("profit", None)
    return data
