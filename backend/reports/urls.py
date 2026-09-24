from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("reports/profit-loss/", views.ProfitLossView.as_view(), name="report-pl"),
    path("reports/stock-valuation/", views.StockValuationView.as_view(), name="report-stock"),
    path("reports/sales/", views.SalesReportView.as_view(), name="report-sales"),
    path("reports/expenses/", views.ExpensesReportView.as_view(), name="report-expenses"),
    path("reports/account-summary/", views.AccountSummaryView.as_view(), name="report-account-summary"),
    path("reports/export/", views.ExportView.as_view(), name="report-export"),
]
