from django.contrib import admin
from django.urls import path
from reports import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    path("excess/", views.excess_inventory, name="excess_inventory"),
    path("obsolete/", views.obsolete_inventory, name="obsolete_inventory"),
    path("inventory-report/", views.inventory_report, name="inventory_report"),
]
