from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [

    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Products
    path('products/',                 views.product_list,   name='product_list'),
    path('products/add/',             views.product_create, name='product_create'),
    path('products/<int:pk>/',        views.product_detail, name='product_detail'),
    path('products/<int:pk>/edit/',   views.product_edit,   name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),

    # Categories
    path('categories/',     views.category_list,   name='category_list'),
    path('categories/add/', views.category_create, name='category_create'),

    # Stock
    path('stock/',               views.stock_list,      name='stock_list'),
    path('stock/movements/',     views.movement_list,   name='movement_list'),
    path('stock/movements/add/', views.movement_create, name='movement_create'),

    # Suppliers
    path('suppliers/',              views.supplier_list,   name='supplier_list'),
    path('suppliers/add/',          views.supplier_create, name='supplier_create'),
    path('suppliers/<int:pk>/delete/', views.supplier_delete, name='supplier_delete'),

    # Purchase Orders
    path('orders/',                       views.order_list,          name='order_list'),
    path('orders/create/',                views.order_create,        name='order_create'),
    path('orders/<int:pk>/',              views.order_detail,        name='order_detail'),
    path('orders/<int:pk>/status/',       views.order_update_status, name='order_update_status'),
    path('orders/<int:pk>/delete/',       views.order_delete,        name='order_delete'),

]
