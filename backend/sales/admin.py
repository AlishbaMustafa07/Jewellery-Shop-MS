from django.contrib import admin

from .models import Invoice, OldGoldIntake, Payment, SaleLine


class SaleLineInline(admin.TabularInline):
    model = SaleLine
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["number", "date", "customer", "net_amount", "balance", "status"]
    list_filter = ["status"]
    search_fields = ["number", "customer__name"]
    inlines = [SaleLineInline]


admin.site.register(Payment)
admin.site.register(OldGoldIntake)
