from rest_framework import serializers

from core.models import HeadOfAccount, ShopSettings

from .models import CashBookEntry, DayClose


class CashBookEntrySerializer(serializers.ModelSerializer):
    hoa_name = serializers.CharField(source="hoa.name", read_only=True)
    sub_hoa_name = serializers.CharField(source="sub_hoa.name", read_only=True, default=None)
    report_group = serializers.CharField(source="hoa.report_group", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True, default=None)

    class Meta:
        model = CashBookEntry
        fields = [
            "id", "date", "type", "hoa", "hoa_name", "sub_hoa", "sub_hoa_name", "report_group", "detail",
            "debited_to", "party", "book_no", "page_no", "pound_weight", "pasa_weight", "rate", "amount",
            "source_type", "source_id", "cash_account", "notes", "is_voided", "void_reason", "day_locked",
            "created_by_name", "created_at", "updated_at",
        ]
        read_only_fields = ["source_type", "source_id", "is_voided", "void_reason", "day_locked", "type"]

    def validate(self, attrs):
        hoa = attrs.get("hoa", getattr(self.instance, "hoa", None))
        sub = attrs.get("sub_hoa", getattr(self.instance, "sub_hoa", None))
        amount = attrs.get("amount", getattr(self.instance, "amount", None))
        if hoa is None:
            raise serializers.ValidationError({"hoa": "Choose a head of account."})
        if hoa.parent_id:
            raise serializers.ValidationError({"hoa": "Pick a main head; choose the sub-head separately."})
        if not hoa.is_active and not self.instance:
            raise serializers.ValidationError({"hoa": "This head of account is inactive."})
        if sub and sub.parent_id != hoa.id:
            raise serializers.ValidationError({"sub_hoa": f"'{sub.name}' is not a sub-head of '{hoa.name}'."})
        if amount is not None and amount <= 0:
            raise serializers.ValidationError({"amount": "Amount must be greater than zero."})
        account = attrs.get("cash_account")
        if account and account not in ShopSettings.load().cash_accounts:
            raise serializers.ValidationError({"cash_account": "Unknown cash account."})
        request = self.context.get("request")
        if request and hoa.is_private and not request.user.can_view_private:
            raise serializers.ValidationError({"hoa": "You cannot post to this head of account."})
        attrs["type"] = hoa.type
        return attrs


class DayCloseSerializer(serializers.ModelSerializer):
    locked_by_name = serializers.CharField(source="locked_by.username", read_only=True, default=None)
    reopened_by_name = serializers.CharField(source="reopened_by.username", read_only=True, default=None)

    class Meta:
        model = DayClose
        fields = "__all__"


class DayActionSerializer(serializers.Serializer):
    date = serializers.DateField()
    counted_cash = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)


class VoidEntrySerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200)


def head_ids_for_group(group):
    return list(HeadOfAccount.objects.filter(report_group=group).values_list("id", flat=True))
