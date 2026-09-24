from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AuditLog, GoldRate, HeadOfAccount, ShopSettings, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "first_name", "last_name", "role", "is_active"]
    list_filter = ["role", "is_active"]
    fieldsets = BaseUserAdmin.fieldsets + (("Shop", {"fields": ("role", "phone", "discount_limit")}),)


admin.site.register(ShopSettings)


@admin.register(HeadOfAccount)
class HeadOfAccountAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "type", "report_group", "is_private", "is_active"]
    list_filter = ["type", "report_group", "is_private"]


@admin.register(GoldRate)
class GoldRateAdmin(admin.ModelAdmin):
    list_display = ["date", "buy_rate_per_tola", "sell_rate_per_tola", "entered_by"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user", "action", "entity_type", "entity_repr"]
    list_filter = ["action", "entity_type"]
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
