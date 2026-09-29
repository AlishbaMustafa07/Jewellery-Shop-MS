from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import AuditLog, GoldRate, HeadOfAccount, ShopSettings, User


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "full_name", "email", "phone", "role",
            "discount_limit", "is_active", "last_login", "date_joined", "password",
        ]
        read_only_fields = ["last_login", "date_joined"]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def validate_password(self, value):
        validate_password(value, self.instance)
        return value

    def validate(self, attrs):
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError({"password": "A password is required for new users."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


def permissions_for(user):
    role = user.role
    back_office = role in ("owner", "manager", "accountant")
    return {
        "view_profit": user.can_view_profit,
        "view_private": user.can_view_private,
        "manage_users": role == "owner",
        "manage_settings": role == "owner",
        "investors": role == "owner",
        "zakat": role == "owner",
        "audit_log": role in ("owner", "accountant"),
        "void_invoice": role in ("owner", "manager"),
        "cash_book": True,
        "day_close": back_office,
        "day_reopen": role == "owner",
        "reports": back_office,
        "set_gold_rate": role in ("owner", "manager"),
        "refining": back_office,
        "discount_limit": str(user.effective_discount_limit()) if user.effective_discount_limit() is not None else None,
    }


class MeSerializer(UserSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = [f for f in UserSerializer.Meta.fields if f != "password"] + ["permissions"]

    def get_permissions(self, obj):
        return permissions_for(obj)


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = MeSerializer(self.user).data
        return data


class ShopSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopSettings
        exclude = ["id"]

    def validate_code_prefixes(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Must be an object mapping category -> prefix.")
        prefixes = [str(v).upper() for v in value.values()]
        if len(prefixes) != len(set(prefixes)):
            raise serializers.ValidationError("Each category needs its own unique prefix.")
        for p in prefixes:
            if not p.isalpha() or len(p) > 6:
                raise serializers.ValidationError(f"Prefix '{p}' must be 1-6 letters.")
        return {k: str(v).upper() for k, v in value.items()}

    def validate_cash_accounts(self, value):
        if not isinstance(value, list) or not value or not all(isinstance(v, str) and v for v in value):
            raise serializers.ValidationError("Provide a non-empty list of account names.")
        return value


class HeadOfAccountSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.name", read_only=True, default=None)
    full_name = serializers.CharField(source="__str__", read_only=True)

    class Meta:
        model = HeadOfAccount
        fields = ["id", "name", "parent", "parent_name", "full_name", "type", "report_group", "is_private", "is_active"]

    def validate(self, attrs):
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        type_ = attrs.get("type", getattr(self.instance, "type", None))
        if parent:
            if parent.parent_id:
                raise serializers.ValidationError({"parent": "Only two levels (head and sub-head) are supported."})
            if parent.type != type_:
                raise serializers.ValidationError({"type": "Sub-head must have the same type as its parent."})
            if self.instance and parent.pk == self.instance.pk:
                raise serializers.ValidationError({"parent": "A head cannot be its own parent."})
        return attrs


class GoldRateSerializer(serializers.ModelSerializer):
    entered_by_name = serializers.CharField(source="entered_by.username", read_only=True, default=None)

    class Meta:
        model = GoldRate
        fields = ["id", "date", "buy_rate_per_tola", "sell_rate_per_tola", "entered_by", "entered_by_name", "created_at"]
        read_only_fields = ["entered_by", "created_at"]
        # Uniqueness is handled in the view, because today's rate may be corrected.
        validators = []
        extra_kwargs = {"date": {"validators": []}}

    def validate(self, attrs):
        if attrs["buy_rate_per_tola"] <= 0 or attrs["sell_rate_per_tola"] <= 0:
            raise serializers.ValidationError("Rates must be greater than zero.")
        return attrs


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ["id", "entity_type", "entity_id", "entity_repr", "action", "user", "user_name", "changes", "note", "created_at"]
