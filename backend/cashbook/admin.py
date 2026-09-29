from django.contrib import admin

from .models import CashBookEntry, DayClose


@admin.register(CashBookEntry)
class CashBookEntryAdmin(admin.ModelAdmin):
    list_display = ["date", "type", "hoa", "sub_hoa", "party", "amount", "cash_account", "is_voided", "day_locked"]
    list_filter = ["type", "cash_account", "source_type", "is_voided"]
    search_fields = ["party", "detail"]


admin.site.register(DayClose)
