from rest_framework.routers import DefaultRouter

from .views import CashBookViewSet

router = DefaultRouter()
router.register("cash-book", CashBookViewSet, basename="cash-book")
urlpatterns = router.urls
