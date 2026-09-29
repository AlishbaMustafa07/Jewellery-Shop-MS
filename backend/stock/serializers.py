from rest_framework import serializers

from core import calculations as calc
from core.models import GoldRate

from .models import StockItem

COST_FIELDS = ("purchase_rate", "gold_price", "extra_costs", "total_cost")


class StockItemSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default=None)
    photo_url = serializers.SerializerMethodField()
    value_at_today = serializers.SerializerMethodField()
    code = serializers.CharField(max_length=20, required=False, allow_blank=True)

    class Meta:
        model = StockItem
        fields = [
            "id", "code", "metal", "category", "name", "pieces", "type", "size", "design", "supplier",
            "supplier_name", "nature", "source_type", "book_no", "page_no", "gross_weight", "big_stone_weight",
            "pd_diamond_weight", "extra_less_gold", "gold_weight", "ratti_kaat", "pasa", "purchase_rate",
            "gold_price", "extra_costs", "total_cost", "value_at_today", "status", "photo", "photo_url",
            "purchase_date", "sold_date", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["gold_weight", "pasa", "gold_price", "total_cost", "photo", "sold_date", "status"]

    def get_photo_url(self, obj):
        if not obj.photo:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.photo.url) if request else obj.photo.url

    def _today_sell_rate(self):
        if "_rate" not in self.context:
            rate = GoldRate.objects.order_by("-date").first()
            self.context["_rate"] = rate.sell_rate_per_tola if rate else None
        return self.context["_rate"]

    def get_value_at_today(self, obj):
        rate = self._today_sell_rate()
        if rate is None or obj.metal != StockItem.Metal.GOLD:
            return None
        return str(calc.value_of_pasa(obj.pasa, rate))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request and not request.user.can_view_profit:
            for f in COST_FIELDS:
                data.pop(f, None)
        return data

    def validate_code(self, value):
        value = (value or "").strip().upper()
        if value:
            qs = StockItem.objects.filter(code=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(f"Code {value} is already used.")
        return value

    def validate(self, attrs):
        get = lambda k: attrs.get(k, getattr(self.instance, k, None) if self.instance else None)  # noqa: E731
        gross = get("gross_weight")
        if gross is not None and gross <= 0:
            raise serializers.ValidationError({"gross_weight": "Gross weight must be greater than zero."})
        ratti = get("ratti_kaat")
        if ratti is not None and not (0 < ratti <= 96):
            raise serializers.ValidationError({"ratti_kaat": "Ratti kaat must be between 0 and 96."})
        gw = calc.gold_weight(gross or 0, get("big_stone_weight"), get("pd_diamond_weight"), get("extra_less_gold"))
        if gross is not None and gw < 0:
            raise serializers.ValidationError({"gross_weight": "Stone/diamond weights exceed the gross weight."})
        request = self.context.get("request")
        if request and not request.user.can_view_profit:
            # Staff can register items but never see or change purchase costs.
            if self.instance:
                for f in ("purchase_rate", "extra_costs"):
                    attrs.pop(f, None)
        if not self.instance and not attrs.get("purchase_rate"):
            rate = GoldRate.for_date(attrs.get("purchase_date") or calc_today())
            if rate:
                attrs["purchase_rate"] = rate.buy_rate_per_tola
        return attrs


def calc_today():
    from django.utils import timezone

    return timezone.localdate()


class StockCalcSerializer(serializers.Serializer):
    """Input for a live cost preview while entering an item."""

    gross_weight = serializers.DecimalField(max_digits=10, decimal_places=3)
    big_stone_weight = serializers.DecimalField(max_digits=10, decimal_places=3, default=0)
    pd_diamond_weight = serializers.DecimalField(max_digits=10, decimal_places=3, default=0)
    extra_less_gold = serializers.DecimalField(max_digits=10, decimal_places=3, default=0)
    ratti_kaat = serializers.DecimalField(max_digits=5, decimal_places=2)
    purchase_rate = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
    extra_costs = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
