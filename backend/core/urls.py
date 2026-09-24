from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register("users", views.UserViewSet, basename="user")
router.register("heads-of-account", views.HeadOfAccountViewSet, basename="head-of-account")
router.register("gold-rates", views.GoldRateViewSet, basename="gold-rate")
router.register("audit-log", views.AuditLogViewSet, basename="audit-log")

urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("auth/change-password/", views.ChangePasswordView.as_view(), name="change-password"),
    path("settings/", views.ShopSettingsView.as_view(), name="settings"),
] + router.urls
