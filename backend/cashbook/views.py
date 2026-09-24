from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from django_filters import rest_framework as filters
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core import audit
from core.exceptions import BusinessRuleError
from core.exporting import export
from core.permissions import ALL_ROLES, MANAGER, OWNER, ACCOUNTANT, roles

from . import services
from .models import CashBookEntry, DayClose
from .serializers import (
    CashBookEntrySerializer,
    DayActionSerializer,
    DayCloseSerializer,
    VoidEntrySerializer,
    head_ids_for_group,
)

SAVED_VIEWS = {
    "shop_expenses": "Shop expenses",
    "home": "Home",
    "zakat": "Zakat",
    "oj": "OJ",
    "shopjew": "Shopjew",
    "refine": "Refine",
    "sales": "Sales receipts",
    "investors": "Investors",
    "shop_purchase": "Shop purchase",
}
PRIVATE_VIEWS = {"home", "zakat", "investors"}

EXPORT_COLUMNS = [
    ("date", "Date"), ("type", "I/E"), ("hoa_name", "Head"), ("sub_hoa_name", "Sub-head"), ("detail", "Detail"),
    ("debited_to", "Debited to"), ("party", "Party"), ("book_no", "Book"), ("page_no", "Page"),
    ("cash_account", "Account"), ("amount", "Amount"),
]


class EntryFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="date", lookup_expr="lte")
    head = filters.UUIDFilter(method="filter_head")
    report_group = filters.CharFilter(field_name="hoa__report_group")

    class Meta:
        model = CashBookEntry
        fields = ["date", "type", "hoa", "sub_hoa", "cash_account", "source_type", "is_voided"]

    def filter_head(self, qs, name, value):
        return qs.filter(Q(hoa_id=value) | Q(sub_hoa_id=value))


def _totals(qs):
    live = qs.filter(is_voided=False)
    inc = live.filter(type="I").aggregate(t=Sum("amount"))["t"] or Decimal("0")
    exp = live.filter(type="E").aggregate(t=Sum("amount"))["t"] or Decimal("0")
    return {"income": inc, "expenditure": exp, "net": inc - exp, "count": qs.count()}


def _export_rows(qs):
    return [
        {**{k: getattr(e, k) for k in ("date", "type", "detail", "debited_to", "party", "book_no", "page_no",
                                       "cash_account", "amount")},
         "hoa_name": e.hoa.name, "sub_hoa_name": e.sub_hoa.name if e.sub_hoa else ""}
        for e in qs
    ]


class CashBookViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                      mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = CashBookEntrySerializer
    permission_classes = [roles(*ALL_ROLES)]
    filterset_class = EntryFilter
    search_fields = ["party", "detail", "debited_to", "notes", "book_no", "hoa__name", "sub_hoa__name"]
    ordering_fields = ["date", "amount", "created_at"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = CashBookEntry.objects.select_related("hoa", "sub_hoa", "created_by")
        if not self.request.user.can_view_private:
            qs = qs.filter(hoa__is_private=False)
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        fmt = request.query_params.get("format")
        if fmt:
            t = _totals(qs)
            resp = export(fmt, "cash-book", "Cash book", EXPORT_COLUMNS, _export_rows(qs.order_by("date", "created_at")),
                          {"hoa_name": f"In {t['income']:,.0f} / Out {t['expenditure']:,.0f}", "amount": t["net"]})
            if resp:
                return resp
        response = super().list(request, *args, **kwargs)
        response.data["totals"] = _totals(qs)
        return response

    @transaction.atomic
    def perform_create(self, serializer):
        date = serializer.validated_data["date"]
        services.assert_day_open(date)
        if date > timezone.localdate():
            raise BusinessRuleError("Cash book entries cannot be dated in the future.")
        entry = serializer.save(created_by=self.request.user, updated_by=self.request.user,
                                source_type=CashBookEntry.Source.MANUAL)
        audit.log_create(self.request.user, entry)

    @transaction.atomic
    def perform_update(self, serializer):
        entry = serializer.instance
        if entry.source_type != CashBookEntry.Source.MANUAL:
            raise BusinessRuleError("Automatic entries change through their source (sale, payment...), not here.")
        if entry.is_voided:
            raise BusinessRuleError("Voided entries cannot be edited.")
        services.assert_day_open(entry.date)
        new_date = serializer.validated_data.get("date", entry.date)
        services.assert_day_open(new_date)
        if entry.created_by_id != self.request.user.id and self.request.user.role not in (OWNER, MANAGER, ACCOUNTANT):
            raise BusinessRuleError("You can only edit entries you created.")
        old = audit.snapshot(entry)
        entry = serializer.save(updated_by=self.request.user)
        audit.log_update(self.request.user, entry, old)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def void(self, request, pk=None):
        entry = self.get_object()
        ser = VoidEntrySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if entry.source_type != CashBookEntry.Source.MANUAL:
            raise BusinessRuleError("Void the sale/payment this entry came from instead.")
        if entry.is_voided:
            raise BusinessRuleError("Entry is already voided.")
        services.assert_day_open(entry.date)
        if entry.created_by_id != request.user.id and request.user.role not in (OWNER, MANAGER, ACCOUNTANT):
            raise BusinessRuleError("You can only void entries you created.")
        services.void_or_reverse(entry, request.user, ser.validated_data["reason"])
        entry.refresh_from_db()
        return Response(self.get_serializer(entry).data)

    @action(detail=False, methods=["get"], url_path="day-summary")
    def day_summary(self, request):
        date = parse_date(request.query_params.get("date") or "") or timezone.localdate()
        return Response(services.day_summary(date))

    @action(detail=False, methods=["post"], url_path="day-close", permission_classes=[roles(OWNER, MANAGER, ACCOUNTANT)])
    def day_close(self, request):
        ser = DayActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        dc = services.close_day(ser.validated_data["date"], request.user, ser.validated_data.get("counted_cash"),
                                ser.validated_data.get("notes", ""))
        return Response(DayCloseSerializer(dc).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="day-reopen", permission_classes=[roles(OWNER)])
    def day_reopen(self, request):
        ser = DayActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        dc = services.reopen_day(ser.validated_data["date"], request.user, ser.validated_data.get("reason", ""))
        return Response(DayCloseSerializer(dc).data)

    @action(detail=False, methods=["get"], url_path="day-closes")
    def day_closes(self, request):
        qs = DayClose.objects.select_related("locked_by", "reopened_by")[:120]
        return Response(DayCloseSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path=r"views/(?P<group>[a-z_]+)")
    def saved_view(self, request, group=None):
        if group not in SAVED_VIEWS:
            raise BusinessRuleError(f"Unknown view '{group}'. Available: {', '.join(SAVED_VIEWS)}.")
        if group in PRIVATE_VIEWS and not request.user.can_view_private:
            raise BusinessRuleError("You do not have access to this view.")
        ids = head_ids_for_group(group)
        qs = self.filter_queryset(self.get_queryset()).filter(Q(hoa_id__in=ids) | Q(sub_hoa_id__in=ids))
        by_head = (qs.filter(is_voided=False).values("hoa__name", "sub_hoa__name", "type")
                   .annotate(total=Sum("amount")).order_by("hoa__name", "sub_hoa__name"))
        fmt = request.query_params.get("format")
        if fmt:
            t = _totals(qs)
            resp = export(fmt, f"cash-book-{group}", f"Cash book - {SAVED_VIEWS[group]}", EXPORT_COLUMNS,
                          _export_rows(qs.filter(is_voided=False).order_by("date")), {"amount": t["net"]})
            if resp:
                return resp
        page = self.paginate_queryset(qs)
        response = self.get_paginated_response(self.get_serializer(page, many=True).data)
        response.data["title"] = SAVED_VIEWS[group]
        response.data["totals"] = _totals(qs)
        response.data["by_head"] = list(by_head)
        return response

    @action(detail=False, methods=["get"], url_path="saved-views")
    def saved_views(self, request):
        return Response([
            {"key": k, "title": v} for k, v in SAVED_VIEWS.items()
            if k not in PRIVATE_VIEWS or request.user.can_view_private
        ])

    @action(detail=False, methods=["get"])
    def balances(self, request):
        date = parse_date(request.query_params.get("date") or "") or timezone.localdate()
        s = services.day_summary(date)
        return Response({acc: v["closing"] for acc, v in s["breakdown"].items()})
