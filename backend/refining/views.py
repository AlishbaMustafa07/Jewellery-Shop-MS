from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import ACCOUNTANT, MANAGER, OWNER, roles

from . import services
from .models import RefineLot, RefineLotItem

BackOffice = roles(OWNER, MANAGER, ACCOUNTANT)


class RefineLotItemSerializer(serializers.ModelSerializer):
    stock_code = serializers.CharField(source="stock_item.code", read_only=True, default=None)
    invoice_number = serializers.CharField(source="old_gold_intake.invoice.number", read_only=True, default=None)

    class Meta:
        model = RefineLotItem
        fields = ["id", "stock_item", "stock_code", "old_gold_intake", "invoice_number", "weight", "pasa"]


class RefineLotSerializer(serializers.ModelSerializer):
    items = RefineLotItemSerializer(many=True, read_only=True)
    loss_pasa = serializers.DecimalField(max_digits=12, decimal_places=4, read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True, default=None)

    class Meta:
        model = RefineLot
        fields = ["id", "date", "refiner", "weight_sent", "expected_pasa", "pasa_returned", "returned_date", "cost",
                  "cost_cash_account", "status", "notes", "loss_pasa", "items", "created_by_name", "created_at"]


class RefineLotCreateSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)
    refiner = serializers.CharField(max_length=100)
    stock_items = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    old_gold = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    weight_sent = serializers.DecimalField(max_digits=10, decimal_places=3, required=False, allow_null=True)
    expected_pasa = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class RefineLotUpdateSerializer(serializers.Serializer):
    refiner = serializers.CharField(max_length=100, required=False)
    pasa_returned = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True,
                                             min_value=0)
    returned_date = serializers.DateField(required=False)
    cost = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=0)
    cost_cash_account = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class RefineLotViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = RefineLotSerializer
    permission_classes = [BackOffice]
    filterset_fields = ["status", "refiner"]
    search_fields = ["refiner", "notes"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return RefineLot.objects.prefetch_related("items__stock_item", "items__old_gold_intake__invoice")

    def create(self, request):
        ser = RefineLotCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        lot = services.create_lot(ser.validated_data, request.user)
        return Response(RefineLotSerializer(self.get_queryset().get(pk=lot.pk)).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        ser = RefineLotUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        lot = services.record_return(self.get_object(), ser.validated_data, request.user)
        return Response(RefineLotSerializer(self.get_queryset().get(pk=lot.pk)).data)

    @action(detail=True, methods=["post"], url_path=r"items/(?P<item_id>\d+)/remove")
    def remove_item(self, request, pk=None, item_id=None):
        lot = services.remove_item(self.get_object(), item_id, request.user)
        return Response(RefineLotSerializer(self.get_queryset().get(pk=lot.pk)).data)


class RefineBalanceView(APIView):
    permission_classes = [BackOffice]

    def get(self, request):
        return Response(services.refine_balance())
