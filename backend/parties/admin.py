from django.contrib import admin

from .models import Customer, Supplier, SupplierTransaction


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "balance"]
    search_fields = ["name", "phone"]


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "type", "phone", "balance"]
    list_filter = ["type"]


admin.site.register(SupplierTransaction)
