import datetime

from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import BusinessRuleError
from core.exporting import export
from core.permissions import ACCOUNTANT, ALL_ROLES, MANAGER, OWNER, roles

from . import full_export, services

ProfitViewers = roles(OWNER, MANAGER)
BackOffice = roles(OWNER, MANAGER, ACCOUNTANT)


def period(request, default_days=None):
    """date_from/date_to from the query string; defaults to the current month."""
    today = timezone.localdate()
    date_from = parse_date(request.query_params.get("date_from") or "")
    date_to = parse_date(request.query_params.get("date_to") or "") or today
    if not date_from:
        date_from = today - datetime.timedelta(days=default_days) if default_days else today.replace(day=1)
    if date_from > date_to:
        raise BusinessRuleError("date_from must be on or before date_to.")
    return date_from, date_to


def _period_label(df, dt):
    return f"{df:%d/%m/%Y} to {dt:%d/%m/%Y}"


class DashboardView(APIView):
    permission_classes = [roles(*ALL_ROLES)]

    def get(self, request):
        return Response(services.dashboard(request.user))


class ProfitLossView(APIView):
    permission_classes = [ProfitViewers]

    def get(self, request):
        return self.report(request, request.query_params.get("format"))

    def report(self, request, fmt):
        df, dt = period(request)
        data = services.profit_loss(df, dt)
        resp = pl_export(fmt, data)
        return resp or Response(data)


def pl_export(fmt, data):
    rows = [
        {"item": "Net sales", "amount": data["net_sales"]},
        {"item": "Cost of goods sold", "amount": -data["cost_of_goods_sold"]},
        {"item": "Gross profit", "amount": data["gross_profit"]},
    ]
    rows += [{"item": f"Other income: {r['head']}", "amount": r["total"]} for r in data["other_income"]]
    rows += [{"item": f"Expense: {r['head']}", "amount": -r["total"]} for r in data["expenses"]]
    rows.append({"item": "NET PROFIT", "amount": data["net_profit"]})
    rows += [{"item": f"Drawings: {r['head']}", "amount": -r["total"]} for r in data["drawings"]]
    rows += [{"item": f"  Category {c['category']} (sales {c['sales']:,.0f}, cost {c['cost']:,.0f})",
              "amount": c["profit"]} for c in data["by_category"]]
    return export(fmt, "profit-loss", "Profit & Loss", [("item", "Item"), ("amount", "Amount (PKR)")], rows,
                  subtitle=_period_label(data["date_from"], data["date_to"]))


class StockValuationView(APIView):
    permission_classes = [BackOffice]

    def get(self, request):
        return self.report(request, request.query_params.get("format"))

    def report(self, request, fmt):
        days = request.query_params.get("slow_days")
        data = services.stock_valuation(int(days) if days and days.isdigit() else None)
        if not request.user.can_view_profit:
            for g in data["groups"]:
                g.pop("cost"), g.pop("unrealised_gain")
            data["totals"].pop("cost")
            for s in data["slow_moving"]:
                s.pop("total_cost")
        cols = [("metal", "Metal"), ("category", "Category"), ("items", "Items"), ("pieces", "Pieces"),
                ("gross_weight", "Gross wt"), ("pasa", "Pasa"), ("value_at_today", "Value @ today")]
        if request.user.can_view_profit:
            cols += [("cost", "Cost"), ("unrealised_gain", "Unrealised gain")]
        resp = export(fmt, "stock-valuation", "Stock valuation", cols, data["groups"],
                      data["totals"], subtitle=f"Rate {data['rate']} on {data['rate_date']}")
        return resp or Response(data)


class SalesReportView(APIView):
    permission_classes = [BackOffice]

    def get(self, request):
        return self.report(request, request.query_params.get("format"))

    def report(self, request, fmt):
        df, dt = period(request)
        group_by = request.query_params.get("group_by", "day")
        try:
            data = services.sales_report(df, dt, group_by)
        except ValueError as e:
            raise BusinessRuleError(str(e))
        if not request.user.can_view_profit:
            data["totals"].pop("profit", None)
            for r in data["rows"]:
                r.pop("profit", None)
        cols = [("key", group_by.title()), ("invoices", "Invoices"), ("net", "Net sales"),
                ("discount", "Discount"), ("received", "Received"), ("balance", "Balance")]
        if group_by == "category":
            cols = [("key", "Category"), ("items", "Items"), ("weight", "Weight"), ("net", "Sales")]
            if request.user.can_view_profit:
                cols.append(("profit", "Profit"))
        resp = export(fmt, f"sales-by-{group_by}", f"Sales by {group_by}", cols,
                      data["rows"], data["totals"], subtitle=_period_label(df, dt))
        return resp or Response({**data, "date_from": df, "date_to": dt})


class ExpensesReportView(APIView):
    permission_classes = [BackOffice]

    def get(self, request):
        return self.report(request, request.query_params.get("format"))

    def report(self, request, fmt):
        df, dt = period(request)
        data = services.expenses_report(df, dt, include_private=request.user.can_view_private)
        cols = [("head", "Head"), ("sub_head", "Sub-head"), ("group", "Group"), ("count", "Entries"), ("total", "Total")]
        resp = export(fmt, "expenses", "Expenses", cols, data["rows"],
                      {"total": data["total"]}, subtitle=_period_label(df, dt))
        return resp or Response({**data, "date_from": df, "date_to": dt})


class AccountSummaryView(APIView):
    permission_classes = [ProfitViewers]

    def get(self, request):
        df, dt = period(request)
        return Response(services.account_summary(df, dt))


class ExportView(APIView):
    """/reports/export/?type=pl|stock|sales|expenses|full&format=xlsx|csv|html"""

    permission_classes = [BackOffice]

    def get(self, request):
        kind = request.query_params.get("type", "")
        fmt = request.query_params.get("format", "xlsx")
        if kind == "full":
            if request.user.role != OWNER:
                raise BusinessRuleError("Only the owner can download the full data export.")
            return full_export.full_workbook_response()
        views = {"pl": ProfitLossView, "stock": StockValuationView, "sales": SalesReportView,
                 "expenses": ExpensesReportView}
        if kind not in views:
            raise BusinessRuleError("type must be one of pl, stock, sales, expenses, full.")
        view = views[kind]()
        view.request = request
        for perm in view.permission_classes:
            if not perm().has_permission(request, view):
                raise BusinessRuleError("Your role cannot export this report.")
        return view.report(request, fmt)

