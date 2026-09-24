from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("invoices", views.InvoiceViewSet, basename="invoice")
router.register("advances", views.AdvanceViewSet, basename="advance")
router.register("payments", views.PaymentViewSet, basename="payment")
router.register("old-gold", views.OldGoldViewSet, basename="old-gold")

urlpatterns = [
    path("sale-preview/", views.SalePreviewView.as_view(), name="sale-preview"),
] + router.urls
