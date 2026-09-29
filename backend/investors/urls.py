from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import InvestorViewSet, ZakatView

router = DefaultRouter()
router.register("investors", InvestorViewSet, basename="investor")
urlpatterns = [path("zakat/calculate/", ZakatView.as_view(), name="zakat")] + router.urls
