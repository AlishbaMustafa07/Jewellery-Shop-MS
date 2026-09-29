from rest_framework.routers import DefaultRouter

from .views import StockItemViewSet

router = DefaultRouter()
router.register("stock", StockItemViewSet, basename="stock")
urlpatterns = router.urls
