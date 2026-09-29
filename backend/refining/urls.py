from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import RefineBalanceView, RefineLotViewSet

router = DefaultRouter()
router.register("refine-lots", RefineLotViewSet, basename="refine-lot")
urlpatterns = [path("refine/balance/", RefineBalanceView.as_view(), name="refine-balance")] + router.urls
