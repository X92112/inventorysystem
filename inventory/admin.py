from django.contrib import admin
from .models import Category, Supplier, Product, StockMovement, PurchaseOrder, PurchaseOrderItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'total_stock', 'created_at']
    search_fields = ['name']


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'created_at']
    search_fields = ['name', 'email']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display  = ['name', 'sku', 'category', 'supplier', 'stock', 'min_stock', 'price', 'status']
    list_filter   = ['category', 'supplier']
    search_fields = ['name', 'sku']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display  = ['product', 'movement_type', 'quantity', 'created_by', 'created_at']
    list_filter   = ['movement_type']
    search_fields = ['product__name']
    readonly_fields = ['created_at']


class PurchaseOrderItemInline(admin.TabularInline):
    model  = PurchaseOrderItem
    extra  = 1
    fields = ['product', 'quantity', 'unit_price']


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'supplier', 'status', 'total', 'created_at']
    list_filter   = ['status']
    inlines       = [PurchaseOrderItemInline]
    readonly_fields = ['created_at', 'updated_at']