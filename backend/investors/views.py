from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from cashbook import services as cashbook
from core import audit
from core import calculations as calc
from core.exceptions import BusinessRuleError
from core.exporting import export
from core.permissions import IsOwner
from reports import services as reports
from reports.views import period

from .models import Investor, InvestorTransaction

CASH_KEYS = {"investment": "investment", "withdrawal": "investor_withdrawal", "profit_paid": "investor_profit"}


class InvestorTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestorTransaction
        fields = ["id", "investor", "date", "type", "amount", "cash_account", "period_from", "period_to", "notes",
                  "is_voided", "created_at"]
        read_only_fields = ["investor", "is_voided"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value


class InvestorSerializer(serializers.ModelSerializer):
    totals = serializers.SerializerMethodField()

    class Meta:
        model = Investor
        fields = ["id", "name", "phone", "reference", "book_no", "page_no", "share_percent", "notes", "is_active",
                  "totals", "created_at"]

    def get_totals(self, obj):
        return {k: str(v) for k, v in obj.totals().items()}


class InvestorViewSet(audit.AuditedViewSetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                      mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = Investor.objects.all()
    serializer_class = InvestorSerializer
    permission_classes = [IsOwner]
    search_fields = ["name", "reference", "phone"]
    filterset_fields = ["is_active"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def retrieve(self, request, *args, **kwargs):
        inv = self.get_object()
        data = self.get_serializer(inv).data
        data["transactions"] = InvestorTransactionSerializer(inv.transactions.all(), many=True).data
        return Response(data)

    @action(detail=True, methods=["get", "post"])
    @transaction.atomic
    def transactions(self, request, pk=None):
        investor = self.get_object()
        if request.method == "GET":
            return Response(InvestorTransactionSerializer(investor.transactions.all(), many=True).data)
        ser = InvestorTransactionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if d["type"] == "withdrawal" and d["amount"] > investor.totals()["capital"]:
            raise BusinessRuleError("Withdrawal exceeds the investor's capital.")
        txn = ser.save(investor=investor, created_by=request.user)
        entry = cashbook.post_entry(
            key=CASH_KEYS[txn.type], date=txn.date, amount=txn.amount, user=request.user, source_type="investor",
            source_id=txn.id, party=investor.name, detail=txn.get_type_display(), cash_account=txn.cash_account,
            debited_to=investor.name, notes=txn.notes, book_no=investor.book_no, page_no=investor.page_no,
        )
        txn.cash_book_entry = entry
        txn.save(update_fields=["cash_book_entry"])
        audit.log_create(request.user, txn)
        return Response(InvestorTransactionSerializer(txn).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path=r"transactions/(?P<txn_id>[^/.]+)/void")
    @transaction.atomic
    def void_transaction(self, request, pk=None, txn_id=None):
        txn = self.get_object().transactions.get(pk=txn_id)
        if txn.is_voided:
            raise BusinessRuleError("Already voided.")
        reason = request.data.get("reason") or "Voided"
        txn.is_voided = True
        txn.save(update_fields=["is_voided", "updated_at"])
        if txn.cash_book_entry:
            cashbook.void_or_reverse(txn.cash_book_entry, request.user, reason)
        audit.log(request.user, "void", txn, note=reason)
        return Response(InvestorTransactionSerializer(txn).data)

    @action(detail=True, methods=["get"])
    def statement(self, request, pk=None):
        investor = self.get_object()
        df = parse_date(request.query_params.get("date_from") or "")
        dt = parse_date(request.query_params.get("date_to") or "")
        balance = Decimal("0")
        rows, opening = [], Decimal("0")
        for t in investor.transactions.filter(is_voided=False).order_by("date", "created_at"):
            delta = t.amount if t.type == "investment" else (-t.amount if t.type == "withdrawal" else Decimal("0"))
            balance += delta
            if df and t.date < df:
                opening = balance
                continue
            if dt and t.date > dt:
                continue
            rows.append({"date": t.date, "type": t.get_type_display(), "notes": t.notes,
                         "investment": t.amount if t.type == "investment" else "",
                         "withdrawal": t.amount if t.type == "withdrawal" else "",
                         "profit_paid": t.amount if t.type == "profit_paid" else "", "capital": balance})
        totals = investor.totals()
        cols = [("date", "Date"), ("type", "Type"), ("notes", "Notes"), ("investment", "Investment"),
                ("withdrawal", "Withdrawal"), ("profit_paid", "Profit paid"), ("capital", "Capital")]
        resp = export(request.query_params.get("format"), f"investor-{investor.name}".replace(" ", "_"),
                      f"Investor statement - {investor.name}", cols, rows,
                      {"notes": "Totals", "capital": totals["capital"], "profit_paid": totals["profit_paid"]},
                      subtitle=f"Share {investor.share_percent}% | Ref {investor.reference} | Book {investor.book_no}/{investor.page_no}")
        return resp or Response({"investor": InvestorSerializer(investor).data, "opening_capital": opening,
                                 "rows": rows, "totals": totals})

    @action(detail=True, methods=["get"], url_path="profit-estimate")
    def profit_estimate(self, request, pk=None):
        """Two candidate methods until the owner confirms which one the Profit sheet uses."""
        investor = self.get_object()
        df, dt = period(request)
        pl = reports.profit_loss(df, dt)
        capital = investor.totals()["capital"]
        months = Decimal((dt.year - df.year) * 12 + dt.month - df.month + 1)
        pct = investor.share_percent / Decimal("100")
        return Response({
            "date_from": df, "date_to": dt, "share_percent": investor.share_percent, "capital": capital,
            "shop_net_profit": pl["net_profit"],
            "share_of_net_profit": calc.q_money(max(pl["net_profit"], Decimal("0")) * pct),
            "percent_of_capital_per_month": calc.q_money(capital * pct * months),
            "months": months,
        })


class ZakatView(APIView):
    permission_classes = [IsOwner]

    def get(self, request):
        date = parse_date(request.query_params.get("date") or "") or timezone.localdate()
        basis = request.query_params.get("basis", "sell")
        if basis not in ("sell", "buy", "cost"):
            raise BusinessRuleError("basis must be sell, buy or cost.")
        deduct = request.query_params.get("deduct_liabilities", "1") != "0"
        try:
            return Response(reports.zakat(date, basis, deduct))
        except ValueError as e:
            raise BusinessRuleError(str(e))
