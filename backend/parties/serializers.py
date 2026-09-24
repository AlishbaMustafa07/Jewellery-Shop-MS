from rest_framework import serializers

from .models import Customer, Supplier, SupplierTransaction


class CustomerSerializer(serializers.ModelSerializer):
    advance_credit = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = ["id", "name", "phone", "address", "notes", "opening_balance", "balance", "advance_credit",
                  "created_at", "updated_at"]
        read_only_fields = ["balance"]

    def get_advance_credit(self, obj):
        if not self.context.get("detail"):
            return None
        return str(obj.advance_credit())

    def validate_phone(self, value):
        return "".join(ch for ch in value if ch.isdigit() or ch == "+")


class SupplierSerializer(serializers.ModelSerializer):
    item_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Supplier
        fields = ["id", "name", "type", "phone", "notes", "opening_balance", "balance", "item_count",
                  "created_at", "updated_at"]
        read_only_fields = ["balance"]


class SupplierTransactionSerializer(serializers.ModelSerializer):
    stock_code = serializers.CharField(source="stock_item.code", read_only=True, default=None)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True, default=None)

    class Meta:
        model = SupplierTransaction
        fields = ["id", "supplier", "date", "type", "amount", "gold_pasa", "stock_item", "stock_code", "method",
                  "cash_account", "notes", "is_voided", "created_by_name", "created_at"]
        read_only_fields = ["supplier", "stock_item", "is_voided"]


class SupplierPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=1)
    method = serializers.ChoiceField(choices=[("cash", "Cash"), ("bank", "Bank"), ("gold", "Gold")], default="cash")
    cash_account = serializers.CharField(required=False, allow_blank=True)
    date = serializers.DateField(required=False)
    gold_pasa = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class SupplierAdjustmentSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=[SupplierTransaction.Type.ADJUSTMENT, SupplierTransaction.Type.LABOUR])
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=1)
    date = serializers.DateField(required=False)
    gold_pasa = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
