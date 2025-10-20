from django.contrib import admin
from django.urls import path
from reports import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    path("excess/", views.excess_inventory, name="excess_inventory"),
    path("obsolete/", views.obsolete_inventory, name="obsolete_inventory"),
    path("inventory-report/", views.inventory_report, name="inventory_report"),
    
    # CRUD operations
    path("add-product/", views.add_product, name="add_product"),
    path("add-stock/", views.add_stock, name="add_stock"),
    path("add-sale/", views.add_sale, name="add_sale"),
    path("edit-product/", views.edit_product, name="edit_product"),
    path("delete-product/", views.delete_product, name="delete_product"),
    
    # Download and utilities
    path("download-csv/", views.download_csv, name="download_csv"),
    path("get-product/<str:product_num>/", views.get_product_details, name="get_product_details"),
]