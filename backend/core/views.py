from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from . import audit
from .exceptions import BusinessRuleError
from .models import AuditLog, GoldRate, HeadOfAccount, ShopSettings, User
from .permissions import ALL_ROLES, IsOwnerOrAccountant, OWNER, MANAGER, ACCOUNTANT, roles
from .serializers import (
    AuditLogSerializer,
    GoldRateSerializer,
    HeadOfAccountSerializer,
    LoginSerializer,
    MeSerializer,
    ShopSettingsSerializer,
    UserSerializer,
)


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            user = User.objects.get(username=request.data.get("username"))
            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])
            audit.log(user, AuditLog.Action.LOGIN, user, note="Logged in")
        return response


class LogoutView(APIView):
    def post(self, request):
        try:
            RefreshToken(request.data.get("refresh")).blacklist()
        except TokenError:
            pass
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)


class ChangePasswordView(APIView):
    def post(self, request):
        user = request.user
        if not user.check_password(request.data.get("old_password", "")):
            raise BusinessRuleError("Current password is incorrect.")
        ser = UserSerializer(user, data={"password": request.data.get("new_password")}, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        audit.log(user, AuditLog.Action.UPDATE, user, note="Changed own password")
        return Response({"detail": "Password changed."})


class UserViewSet(audit.AuditedViewSetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                  mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = User.objects.all().order_by("username")
    serializer_class = UserSerializer
    # Everyone in the back office can list users (salesperson filters); only the owner changes them.
    permission_classes = [roles(OWNER, read=(OWNER, MANAGER, ACCOUNTANT))]
    search_fields = ["username", "first_name", "last_name", "phone"]
    filterset_fields = ["role", "is_active"]

    def perform_update(self, serializer):
        if serializer.instance == self.request.user and serializer.validated_data.get("is_active") is False:
            raise BusinessRuleError("You cannot deactivate your own account.")
        if (serializer.instance == self.request.user and "role" in serializer.validated_data
                and serializer.validated_data["role"] != OWNER):
            raise BusinessRuleError("You cannot remove your own owner role.")
        super().perform_update(serializer)


class ShopSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = ShopSettingsSerializer
    permission_classes = [roles(OWNER, read=ALL_ROLES)]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return ShopSettings.load()

    def perform_update(self, serializer):
        old = audit.snapshot(serializer.instance)
        instance = serializer.save()
        audit.log_update(self.request.user, instance, old)


class HeadOfAccountViewSet(audit.AuditedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = HeadOfAccountSerializer
    permission_classes = [roles(OWNER, MANAGER, ACCOUNTANT, read=ALL_ROLES)]
    filterset_fields = ["type", "parent", "report_group", "is_active", "is_private"]
    search_fields = ["name"]
    pagination_class = None

    def get_queryset(self):
        qs = HeadOfAccount.objects.select_related("parent")
        if not self.request.user.can_view_private:
            qs = qs.filter(is_private=False)
        if self.request.query_params.get("top_level") == "1":
            qs = qs.filter(parent__isnull=True)
        return qs

    def perform_destroy(self, instance):
        if instance.entries.exists() or instance.sub_entries.exists() or instance.children.exists():
            instance.is_active = False
            instance.save(update_fields=["is_active"])
            audit.log(self.request.user, AuditLog.Action.UPDATE, instance, note="Deactivated (has entries)")
            return
        super().perform_destroy(instance)


class GoldRateFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = GoldRate
        fields = ["date"]


class GoldRateViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                      viewsets.GenericViewSet):
    queryset = GoldRate.objects.select_related("entered_by")
    serializer_class = GoldRateSerializer
    permission_classes = [roles(OWNER, MANAGER, read=ALL_ROLES)]
    filterset_class = GoldRateFilter

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        date = ser.validated_data["date"]
        existing = GoldRate.objects.filter(date=date).first()
        if existing:
            # Past rates are never overwritten; only today's rate may be corrected.
            if date != timezone.localdate():
                raise BusinessRuleError(f"A rate for {date:%d/%m/%Y} already exists and past rates cannot be changed.")
            old = audit.snapshot(existing)
            existing.buy_rate_per_tola = ser.validated_data["buy_rate_per_tola"]
            existing.sell_rate_per_tola = ser.validated_data["sell_rate_per_tola"]
            existing.entered_by = request.user
            existing.save()
            audit.log_update(request.user, existing, old, note="Corrected today's rate")
            return Response(self.get_serializer(existing).data)
        if date > timezone.localdate():
            raise BusinessRuleError("Cannot set a rate for a future date.")
        rate = ser.save(entered_by=request.user)
        audit.log_create(request.user, rate)
        return Response(self.get_serializer(rate).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def today(self, request):
        today = timezone.localdate()
        rate = GoldRate.for_date(today)
        if not rate:
            return Response({"detail": "No gold rate has been entered yet.", "is_today": False, "rate": None})
        data = self.get_serializer(rate).data
        return Response({"is_today": rate.date == today, "rate": data, "detail": ""})


class AuditLogFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = AuditLog
        fields = ["entity_type", "entity_id", "user", "action"]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("user")
    serializer_class = AuditLogSerializer
    permission_classes = [IsOwnerOrAccountant]
    filterset_class = AuditLogFilter
    search_fields = ["entity_repr", "note", "entity_id"]
