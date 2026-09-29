from django.contrib import admin

from .models import RefineLot, RefineLotItem


class RefineLotItemInline(admin.TabularInline):
    model = RefineLotItem
    extra = 0


@admin.register(RefineLot)
class RefineLotAdmin(admin.ModelAdmin):
    list_display = ["date", "refiner", "weight_sent", "expected_pasa", "pasa_returned", "cost", "status"]
    inlines = [RefineLotItemInline]
