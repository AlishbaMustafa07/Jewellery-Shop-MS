from django.contrib import admin

from .models import StockItem


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ["code", "metal", "category", "gross_weight", "pasa", "total_cost", "status"]
    list_filter = ["metal", "status", "category"]
    search_fields = ["code", "name", "design"]
