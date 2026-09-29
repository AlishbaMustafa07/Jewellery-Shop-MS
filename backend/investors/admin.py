from django.contrib import admin

from .models import Investor, InvestorTransaction


@admin.register(Investor)
class InvestorAdmin(admin.ModelAdmin):
    list_display = ["name", "reference", "share_percent", "is_active"]


admin.site.register(InvestorTransaction)
