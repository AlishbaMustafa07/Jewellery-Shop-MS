from django.db.models import Count
from django.shortcuts import render
from django_filters import rest_framework as filters
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import BusinessRuleError
from core.models import ShopSettings
from core.permissions import ALL_ROLES, MANAGER, OWNER, roles
from parties.models import Customer

from . import services
from .models import Invoice, OldGoldIntake, Payment
from .serializers import (
    InvoiceDetailSerializer,
    InvoiceInputSerializer,
    InvoiceListSerializer,
    OldGoldSerializer,
    PaymentInputSerializer,
    PaymentSerializer,
    VoidSerializer,
    preview_to_json,
)


class InvoiceFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="date", lookup_expr="lte")
    has_balance = filters.BooleanFilter(method="filter_balance")

    class Meta:
        model = Invoice
        fields = ["status", "customer", "salesperson", "number"]

    def filter_balance(self, qs, name, value):
        return qs.filter(balance__gt=0) if value else qs.filter(balance__lte=0)


class InvoiceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [roles(*ALL_ROLES)]
    filterset_class = InvoiceFilter
    search_fields = ["number", "customer__name", "customer__phone", "customer_name", "customer_phone",
                     "lines__stock_item__code", "legacy_book"]
    ordering_fields = ["date", "number", "net_amount", "balance"]

    def get_queryset(self):
        qs = Invoice.objects.select_related("customer", "salesperson", "voided_by")
        if self.action == "list":
            return qs.annotate(line_count=Count("lines", distinct=True)).distinct()
        return qs.prefetch_related("lines__stock_item", "payments__created_by", "old_gold")

    def get_serializer_class(self):
        return InvoiceListSerializer if self.action == "list" else InvoiceDetailSerializer

    def create(self, request):
        ser = InvoiceInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        invoice = services.create_invoice(ser.validated_data, request.user)
        invoice = self.get_queryset().get(pk=invoice.pk)
        return Response(InvoiceDetailSerializer(invoice, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[roles(OWNER, MANAGER)])
    def void(self, request, pk=None):
        ser = VoidSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        invoice = services.void_invoice(self.get_object(), request.user, ser.validated_data["reason"])
        return Response(InvoiceDetailSerializer(invoice, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def payments(self, request, pk=None):
        ser = PaymentInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.add_payment(self.get_object(), ser.validated_data, request.user)
        invoice = self.get_queryset().get(pk=pk)
        return Response(InvoiceDetailSerializer(invoice, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def receipt(self, request, pk=None):
        invoice = self.get_object()
        size = request.query_params.get("size", "a4")
        return render(request, "print/receipt.html", {
            "invoice": invoice,
            "lines": invoice.lines.all(),
            "payments": invoice.payments.filter(is_voided=False),
            "old_gold": invoice.old_gold.all(),
            "shop": ShopSettings.load(),
            "size": "80mm" if size.lower() in ("80", "80mm", "thermal") else "a4",
        })


class SalePreviewView(APIView):
    permission_classes = [roles(*ALL_ROLES)]

    def post(self, request):
        ser = InvoiceInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        p = services.preview(ser.validated_data)
        return Response(preview_to_json(p, request.user.can_view_profit))


class PaymentFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = Payment
        fields = ["customer", "invoice", "kind", "method", "is_voided", "cash_account"]


class AdvanceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [roles(*ALL_ROLES)]
    filterset_class = PaymentFilter
    search_fields = ["customer__name", "customer__phone", "reference", "notes"]

    def get_queryset(self):
        return Payment.objects.filter(kind=Payment.Kind.ADVANCE).select_related("customer", "invoice", "created_by")

    def create(self, request):
        customer_id = request.data.get("customer")
        customer = Customer.objects.filter(pk=customer_id).first() if customer_id else None
        if not customer:
            raise BusinessRuleError("Select the customer who is paying the advance.")
        ser = PaymentInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payment = services.create_advance(customer, ser.validated_data, request.user)
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class PaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [roles(*ALL_ROLES)]
    filterset_class = PaymentFilter
    search_fields = ["customer__name", "invoice__number", "reference"]

    def get_queryset(self):
        return Payment.objects.select_related("customer", "invoice", "created_by")

    @action(detail=True, methods=["post"], permission_classes=[roles(OWNER, MANAGER)])
    def void(self, request, pk=None):
        ser = VoidSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payment = services.void_payment(self.get_object(), request.user, ser.validated_data["reason"])
        return Response(PaymentSerializer(payment).data)


class OldGoldViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = OldGoldSerializer
    permission_classes = [roles(*ALL_ROLES)]
    filterset_fields = ["status"]
    search_fields = ["invoice__number", "description"]

    def get_queryset(self):
        return OldGoldIntake.objects.select_related("invoice__customer").exclude(invoice__status=Invoice.Status.VOIDED)
