from django.db import transaction
from django.db.models import Count, Max, Min, Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from cashbook import services as cashbook
from core import audit
from core.exporting import export
from core.permissions import ALL_ROLES, MANAGER, OWNER, ACCOUNTANT, roles
from sales.models import Invoice, Payment
from sales.serializers import InvoiceListSerializer, PaymentInputSerializer, PaymentSerializer
from sales.services import default_cash_account, receive_customer_payment
from stock.models import StockItem
from stock.serializers import StockItemSerializer

from .models import Customer, Supplier, SupplierTransaction
from .serializers import (
    CustomerSerializer,
    SupplierAdjustmentSerializer,
    SupplierPaymentSerializer,
    SupplierSerializer,
    SupplierTransactionSerializer,
)
from .statements import STATEMENT_COLUMNS, customer_statement, supplier_statement


def _dates(request):
    return parse_date(request.query_params.get("date_from") or ""), parse_date(request.query_params.get("date_to") or "")


def _statement_response(request, name, statement):
    date_from, date_to = _dates(request)
    period = " to ".join(d.strftime("%d/%m/%Y") for d in (date_from, date_to) if d) or "All dates"
    fmt = request.query_params.get("format")
    totals = {"description": "Totals / closing", "debit": statement["total_debit"],
              "credit": statement["total_credit"], "balance": statement["closing_balance"]}
    rows = [{"date": date_from, "type": "", "ref": "", "description": "Opening balance",
             "debit": "", "credit": "", "balance": statement["opening_balance"]}] + statement["rows"]
    resp = export(fmt, f"statement-{name}".replace(" ", "_"), f"Account statement - {name}",
                  STATEMENT_COLUMNS, rows, totals, subtitle=period)
    return resp or Response(statement)


class CustomerViewSet(audit.AuditedViewSetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                      mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [roles(*ALL_ROLES)]
    search_fields = ["name", "phone", "address"]
    ordering_fields = ["name", "balance", "created_at"]
    filterset_fields = ["phone"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = Customer.objects.all()
        if self.request.query_params.get("with_balance") == "1":
            qs = qs.filter(balance__gt=0)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["detail"] = self.action != "list"
        return ctx

    @transaction.atomic
    def perform_update(self, serializer):
        if "opening_balance" in serializer.validated_data and self.request.user.role not in (OWNER, MANAGER, ACCOUNTANT):
            serializer.validated_data.pop("opening_balance")
        super().perform_update(serializer)
        serializer.instance.recompute_balance()

    @transaction.atomic
    def perform_create(self, serializer):
        super().perform_create(serializer)
        serializer.instance.recompute_balance()

    def retrieve(self, request, *args, **kwargs):
        customer = self.get_object()
        data = self.get_serializer(customer).data
        ctx = {"request": request}
        invoices = Invoice.objects.filter(customer=customer).select_related("salesperson", "customer").order_by("-date")
        data["invoices"] = InvoiceListSerializer(invoices[:200], many=True, context=ctx).data
        data["payments"] = PaymentSerializer(
            Payment.objects.filter(customer=customer).select_related("invoice", "created_by")[:200], many=True).data
        return Response(data)

    @action(detail=True, methods=["get"])
    def statement(self, request, pk=None):
        customer = self.get_object()
        return _statement_response(request, customer.name, customer_statement(customer, *_dates(request)))

    @action(detail=True, methods=["post"])
    def payments(self, request, pk=None):
        ser = PaymentInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        created = receive_customer_payment(self.get_object(), ser.validated_data, request.user)
        return Response(PaymentSerializer(created, many=True).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="balance-reminders")
    def balance_reminders(self, request):
        today = timezone.localdate()
        qs = (Customer.objects.filter(balance__gt=0)
              .annotate(oldest_open=Min("invoices__date", filter=Q(invoices__balance__gt=0) & ~Q(invoices__status="voided")),
                        last_payment=Max("payments__date", filter=Q(payments__is_voided=False)))
              .order_by("oldest_open", "-balance"))
        rows = []
        for c in qs:
            rows.append({
                "id": str(c.id), "name": c.name, "phone": c.phone, "balance": c.balance,
                "oldest_open": c.oldest_open, "last_payment": c.last_payment,
                "days_outstanding": (today - c.oldest_open).days if c.oldest_open else None,
            })
        rows.sort(key=lambda r: (r["oldest_open"] is None, r["oldest_open"] or today))
        columns = [("name", "Customer"), ("phone", "Phone"), ("balance", "Balance"), ("oldest_open", "Oldest open"),
                   ("days_outstanding", "Days"), ("last_payment", "Last payment")]
        resp = export(request.query_params.get("format"), "balance-reminders", "Customers with outstanding balance",
                      columns, rows, {"balance": sum(r["balance"] for r in rows)})
        return resp or Response(rows)


class SupplierViewSet(audit.AuditedViewSetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                      mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = SupplierSerializer
    permission_classes = [roles(OWNER, MANAGER, ACCOUNTANT, read=ALL_ROLES)]
    search_fields = ["name", "phone"]
    filterset_fields = ["type"]
    ordering_fields = ["name", "balance"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return Supplier.objects.annotate(item_count=Count("items"))

    @transaction.atomic
    def perform_update(self, serializer):
        super().perform_update(serializer)
        serializer.instance.recompute_balance()

    @transaction.atomic
    def perform_create(self, serializer):
        super().perform_create(serializer)
        serializer.instance.recompute_balance()

    def retrieve(self, request, *args, **kwargs):
        supplier = self.get_object()
        data = self.get_serializer(supplier).data
        items = StockItem.objects.filter(supplier=supplier).select_related("supplier").order_by("-created_at")[:300]
        data["items"] = StockItemSerializer(items, many=True, context={"request": request}).data
        data["transactions"] = SupplierTransactionSerializer(
            supplier.transactions.select_related("stock_item", "created_by").order_by("-date", "-created_at")[:300],
            many=True).data
        return Response(data)

    @action(detail=True, methods=["get"])
    def statement(self, request, pk=None):
        supplier = self.get_object()
        return _statement_response(request, supplier.name, supplier_statement(supplier, *_dates(request)))

    @action(detail=True, methods=["post"], permission_classes=[roles(OWNER, MANAGER, ACCOUNTANT)])
    @transaction.atomic
    def payments(self, request, pk=None):
        supplier = self.get_object()
        ser = SupplierPaymentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        date = d.get("date") or timezone.localdate()
        txn = SupplierTransaction.objects.create(
            supplier=supplier, date=date, type=SupplierTransaction.Type.PAYMENT, amount=d["amount"],
            gold_pasa=d.get("gold_pasa"), method=d["method"], notes=d.get("notes", ""), created_by=request.user,
        )
        if d["method"] != "gold":
            account = d.get("cash_account") or default_cash_account(d["method"])
            key = "karigar_payment" if supplier.type == Supplier.Type.KARIGAR else "supplier_payment"
            entry = cashbook.post_entry(
                key=key, date=date, amount=d["amount"], user=request.user, source_type="supplier_payment",
                source_id=txn.id, party=supplier.name, detail=d["method"].title(), cash_account=account,
                notes=d.get("notes", ""),
            )
            txn.cash_account = account
            txn.cash_book_entry = entry
            txn.save(update_fields=["cash_account", "cash_book_entry"])
        supplier.recompute_balance()
        audit.log_create(request.user, txn)
        return Response(SupplierTransactionSerializer(txn).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[roles(OWNER, MANAGER)])
    @transaction.atomic
    def adjustments(self, request, pk=None):
        supplier = self.get_object()
        ser = SupplierAdjustmentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        txn = SupplierTransaction.objects.create(
            supplier=supplier, date=d.get("date") or timezone.localdate(), type=d["type"], amount=d["amount"],
            gold_pasa=d.get("gold_pasa"), notes=d.get("notes", ""), created_by=request.user,
        )
        supplier.recompute_balance()
        audit.log_create(request.user, txn)
        return Response(SupplierTransactionSerializer(txn).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path=r"transactions/(?P<txn_id>[^/.]+)/void",
            permission_classes=[roles(OWNER, MANAGER)])
    @transaction.atomic
    def void_transaction(self, request, pk=None, txn_id=None):
        supplier = self.get_object()
        txn = supplier.transactions.get(pk=txn_id)
        if txn.type == SupplierTransaction.Type.PURCHASE:
            return Response({"detail": "Purchase lines follow the stock item; edit or return the item instead.",
                             "errors": {}}, status=status.HTTP_400_BAD_REQUEST)
        reason = request.data.get("reason", "Voided")
        txn.is_voided = True
        txn.save(update_fields=["is_voided", "updated_at"])
        if txn.cash_book_entry:
            cashbook.void_or_reverse(txn.cash_book_entry, request.user, reason)
        supplier.recompute_balance()
        audit.log(request.user, "void", txn, note=reason)
        return Response(SupplierTransactionSerializer(txn).data)
