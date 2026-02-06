from django.contrib import admin
from .models import Product, Customer, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    readonly_fields = ['get_cost']

    def get_cost(self, obj):
        return obj.get_cost() if obj.pk else '-'
    get_cost.short_description = 'Вартість'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'purchase_price', 'selling_price', 'stock']
    list_filter = ['created_at']
    search_fields = ['name', 'sku']
    list_editable = ['stock', 'selling_price']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'phone', 'source', 'created_at']
    list_filter = ['source', 'created_at']
    search_fields = ['full_name', 'phone', 'email']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'status', 'city', 'get_total_cost', 'created_at']
    list_filter = ['status', 'delivery_service', 'payment_type', 'created_at']
    search_fields = ['customer__full_name', 'customer__phone', 'ttn', 'city']
    inlines = [OrderItemInline]
    readonly_fields = ['get_total_cost', 'get_amount_due', 'get_profit']

    def get_total_cost(self, obj):
        return f"{obj.get_total_cost():.2f} грн"
    get_total_cost.short_description = 'Сума'

    def get_amount_due(self, obj):
        return f"{obj.get_amount_due():.2f} грн"
    get_amount_due.short_description = 'До сплати'

    def get_profit(self, obj):
        return f"{obj.get_profit():.2f} грн"
    get_profit.short_description = 'Прибуток'
