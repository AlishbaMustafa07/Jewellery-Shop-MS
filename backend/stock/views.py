from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django_filters import rest_framework as filters
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from core import audit, barcode
from core import calculations as calc
from core.exceptions import BusinessRuleError
from core.models import GoldRate, ShopSettings
from core.permissions import ALL_ROLES, MANAGER, OWNER, roles

from . import services
from .models import StockItem
from .serializers import StockCalcSerializer, StockItemSerializer


class StockFilter(filters.FilterSet):
    min_weight = filters.NumberFilter(field_name="gross_weight", lookup_expr="gte")
    max_weight = filters.NumberFilter(field_name="gross_weight", lookup_expr="lte")
    date_from = filters.DateFilter(field_name="purchase_date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="purchase_date", lookup_expr="lte")
    category = filters.CharFilter(field_name="category", lookup_expr="iexact")
    status = filters.MultipleChoiceFilter(choices=StockItem.Status.choices)
    code = filters.CharFilter(field_name="code", lookup_expr="iexact")

    class Meta:
        model = StockItem
        fields = ["metal", "category", "status", "supplier", "nature", "type", "source_type", "code"]


class StockItemViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                       mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = StockItemSerializer
    permission_classes = [roles(*ALL_ROLES)]
    filterset_class = StockFilter
    search_fields = ["code", "name", "design", "category", "book_no"]
    ordering_fields = ["code", "gross_weight", "pasa", "purchase_date", "created_at", "total_cost", "category"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return StockItem.objects.select_related("supplier")

    def list(self, request, *args, **kwargs):
        # An exact code match (e.g. scanned tag) jumps straight to the item.
        q = request.query_params.get("search", "").strip().upper()
        if q:
            exact = self.get_queryset().filter(code=q)
            if exact.exists():
                page = self.paginate_queryset(exact)
                return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return super().list(request, *args, **kwargs)

    @transaction.atomic
    def perform_create(self, serializer):
        code = serializer.validated_data.pop("code", "")
        category = serializer.validated_data["category"]
        if code:
            if not (self.request.user.role in (OWNER, MANAGER)):
                raise BusinessRuleError("Only the owner or a manager can set an item code by hand.")
            services.bump_sequence_for(code)
        else:
            code = services.next_code(category)
        item = serializer.save(code=code, created_by=self.request.user, updated_by=self.request.user)
        services.sync_supplier_purchase(item, self.request.user)
        audit.log_create(self.request.user, item)

    @transaction.atomic
    def perform_update(self, serializer):
        item = serializer.instance
        if item.status == StockItem.Status.SOLD and not self.request.user.can_view_profit:
            raise BusinessRuleError("Sold items can only be edited by the owner or a manager.")
        new_code = serializer.validated_data.pop("code", "")
        if new_code and new_code != item.code:
            if self.request.user.role != OWNER:
                raise BusinessRuleError("Only the owner can change an item code.")
            serializer.validated_data["code"] = new_code
        old = audit.snapshot(item)
        item = serializer.save(updated_by=self.request.user)
        services.sync_supplier_purchase(item, self.request.user)
        audit.log_update(self.request.user, item, old)

    @action(detail=False, methods=["get"], url_path="next-code")
    def next_code(self, request):
        category = request.query_params.get("category", "")
        return Response({"category": category, "code": services.preview_code(category)})

    @action(detail=False, methods=["get"])
    def categories(self, request):
        prefixes = ShopSettings.load().code_prefixes
        used = StockItem.objects.values("category").annotate(n=Count("id")).order_by("category")
        counts = {r["category"]: r["n"] for r in used}
        names = sorted(set(prefixes) | set(counts))
        return Response([{"category": c, "prefix": prefixes.get(c), "count": counts.get(c, 0)} for c in names])

    @action(detail=False, methods=["get"])
    def totals(self, request):
        qs = self.filter_queryset(self.get_queryset())
        agg = qs.aggregate(
            items=Count("id"), pieces=Sum("pieces"), gross_weight=Sum("gross_weight"),
            gold_weight=Sum("gold_weight"), pasa=Sum("pasa"), total_cost=Sum("total_cost"),
        )
        gold_pasa = qs.filter(metal=StockItem.Metal.GOLD).aggregate(p=Sum("pasa"))["p"] or Decimal("0")
        rate = GoldRate.objects.order_by("-date").first()
        data = {k: (v if v is not None else 0) for k, v in agg.items()}
        data["value_at_today"] = calc.value_of_pasa(gold_pasa, rate.sell_rate_per_tola) if rate else None
        if not request.user.can_view_profit:
            data.pop("total_cost")
        return Response(data)

    @action(detail=False, methods=["post"])
    def calculate(self, request):
        ser = StockCalcSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        rate = d["purchase_rate"]
        if not rate:
            today = GoldRate.objects.order_by("-date").first()
            rate = today.buy_rate_per_tola if today else Decimal("0")
        values = calc.compute_stock_values(
            d["gross_weight"], d["big_stone_weight"], d["pd_diamond_weight"], d["extra_less_gold"],
            d["ratti_kaat"], rate, d["extra_costs"],
        )
        values["purchase_rate"] = rate
        if not request.user.can_view_profit:
            values = {"gold_weight": values["gold_weight"], "pasa": values["pasa"]}
        return Response(values)

    @action(detail=True, methods=["get"])
    def tag(self, request, pk=None):
        items = [self.get_object()]
        return render(request, "print/tags.html", {"items": _tag_rows(items), "shop": ShopSettings.load()})

    @action(detail=False, methods=["get"], url_path="tags")
    def tags(self, request):
        ids = [i for i in request.query_params.get("ids", "").split(",") if i]
        items = list(self.get_queryset().filter(Q(id__in=ids)).order_by("code"))
        return render(request, "print/tags.html", {"items": _tag_rows(items), "shop": ShopSettings.load()})

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def photo(self, request, pk=None):
        item = self.get_object()
        upload = request.FILES.get("photo")
        if not upload:
            raise BusinessRuleError("Attach an image file in the 'photo' field.")
        if upload.size > 5 * 1024 * 1024:
            raise BusinessRuleError("Photo must be smaller than 5 MB.")
        if not (upload.content_type or "").startswith("image/"):
            raise BusinessRuleError("Only image files are allowed.")
        old = audit.snapshot(item)
        item.photo = upload
        item.updated_by = request.user
        item.save()
        audit.log_update(request.user, item, old, note="Photo uploaded")
        return Response(self.get_serializer(item).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="return-to-supplier",
            permission_classes=[roles(OWNER, MANAGER)])
    @transaction.atomic
    def return_to_supplier(self, request, pk=None):
        item = self.get_object()
        old = audit.snapshot(item)
        services.return_to_supplier(item, request.user, request.data.get("notes", ""))
        audit.log_update(request.user, item, old, note="Returned to supplier")
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=["post"], url_path="set-status", permission_classes=[roles(OWNER, MANAGER)])
    @transaction.atomic
    def set_status(self, request, pk=None):
        """Manual status moves (transferred / back in stock). Sales and refining set status themselves."""
        item = self.get_object()
        new = request.data.get("status")
        allowed = {StockItem.Status.IN_STOCK, StockItem.Status.TRANSFERRED}
        if new not in allowed:
            raise BusinessRuleError("Status can only be set to in_stock or transferred here.")
        if item.status == StockItem.Status.SOLD:
            raise BusinessRuleError("Sold items change status only by voiding the invoice.")
        if item.status == StockItem.Status.SR_REFINE:
            raise BusinessRuleError("Remove the item from its refine lot instead.")
        old = audit.snapshot(item)
        item.status = new
        item.updated_by = request.user
        item.save()
        audit.log_update(request.user, item, old, note=request.data.get("notes", "Status changed"))
        return Response(self.get_serializer(item).data)


def _tag_rows(items):
    return [{"item": it, "barcode": barcode.svg(it.code)} for it in items]
