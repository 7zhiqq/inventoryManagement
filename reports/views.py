from django.shortcuts import render
from datetime import datetime, timedelta
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from django.core.paginator import Paginator

uri = "mongodb+srv://kfgmationg_db_user:sevenzhiq@inventory-management.d9mq3xr.mongodb.net/?retryWrites=true&w=majority&appName=inventory-management"

client = MongoClient(uri, server_api=ServerApi('1'))

db = client["market"]
inventory = db["inventory"]
sales = db["sales"]

def dashboard(request):
    # Cutoff for obsolete (10 months ago)
    cutoff_date = (datetime.now() - timedelta(days=300)).strftime("%Y-%m-%d")

    # Get data with sales info
    all_products = list(inventory.aggregate([
        {
            "$lookup": {
                "from": "sales",
                "localField": "product_num",
                "foreignField": "product_num",
                "as": "sales_info"
            }
        },
        {"$unwind": "$sales_info"},
        {
            "$project": {
                "_id": 0,
                "product_num": 1,
                "item_name": 1,
                "quantity_on_hand": 1,
                "units_sold": "$sales_info.units_sold",
                "last_sales_date": "$sales_info.last_sales_date"
            }
        },
        {"$sort": {"product_num": 1}}
    ]))

    # Process flags
    cutoff_date_obj = datetime.strptime(cutoff_date, "%Y-%m-%d")
    for p in all_products:
        qty = p.get("quantity_on_hand", 0)
        sold = p.get("units_sold", 0)
        last_date_str = p.get("last_sales_date", "N/A")

        # Compute excess qty
        p["excess_qty"] = qty - sold
        p["is_excess"] = p["excess_qty"] > 0

        # Obsolete check
        if last_date_str != "N/A":
            last_date_obj = datetime.strptime(last_date_str, "%Y-%m-%d")
            p["is_obsolete"] = last_date_obj < cutoff_date_obj
        else:
            p["is_obsolete"] = False

    return render(request, "reports/dashboard.html", {
        "products": all_products,
    })

def excess_inventory(request):
    cutoff_date = (datetime.now() - timedelta(days=300)).strftime("%Y-%m-%d")

    all_products = list(inventory.aggregate([
        {
            "$lookup": {
                "from": "sales",
                "localField": "product_num",
                "foreignField": "product_num",
                "as": "sales_info"
            }
        },
        {"$unwind": "$sales_info"},
        {
            "$project": {
                "_id": 0,
                "product_num": 1,
                "item_name": 1,
                "quantity_on_hand": 1,
                "units_sold": "$sales_info.units_sold",
                "last_sales_date": "$sales_info.last_sales_date"
            }
        },
        {"$sort": {"product_num": 1}}
    ]))

    cutoff_date_obj = datetime.strptime(cutoff_date, "%Y-%m-%d")
    excess_items = []

    for p in all_products:
        qty = p.get("quantity_on_hand", 0)
        sold = p.get("units_sold", 0)
        last_date_str = p.get("last_sales_date", "N/A")

        # Compute excess
        p["excess_qty"] = qty - sold
        if p["excess_qty"] > 0:
            excess_items.append(p)

    return render(request, "reports/excess.html", {
        "products": excess_items,
    })

def obsolete_inventory(request):
    # cutoff = 10 months ago
    cutoff_date = (datetime.now() - timedelta(days=300)).strftime("%Y-%m-%d")

    # Get obsolete products from MongoDB
    from .views import inventory, sales  # if already imported globally, no need
    all_products = list(inventory.aggregate([
        {
            "$lookup": {
                "from": "sales",
                "localField": "product_num",
                "foreignField": "product_num",
                "as": "sales_info"
            }
        },
        {"$unwind": "$sales_info"},
        {
            "$project": {
                "_id": 0,
                "product_num": 1,
                "item_name": 1,
                "quantity_on_hand": 1,
                "units_sold": "$sales_info.units_sold",
                "last_sales_date": "$sales_info.last_sales_date"
            }
        }
    ]))

    # Filter obsolete
    cutoff_date_obj = datetime.strptime(cutoff_date, "%Y-%m-%d")
    obsolete_products = []
    for p in all_products:
        if p["last_sales_date"]:
            last_date_obj = datetime.strptime(p["last_sales_date"], "%Y-%m-%d")
            if last_date_obj < cutoff_date_obj:
                obsolete_products.append(p)

    return render(request, "reports/obsolete.html", {
        "products": obsolete_products
    })

def inventory_report(request):
    # Cutoff for obsolete (10 months ago)
    cutoff_date = (datetime.now() - timedelta(days=300)).strftime("%Y-%m-%d")

    all_products = list(inventory.aggregate([
        {
            "$lookup": {
                "from": "sales",
                "localField": "product_num",
                "foreignField": "product_num",
                "as": "sales_info"
            }
        },
        {"$unwind": "$sales_info"},
        {
            "$project": {
                "_id": 0,
                "product_num": 1,
                "item_name": 1,
                "quantity_on_hand": 1,
                "units_sold": "$sales_info.units_sold",
                "last_sales_date": "$sales_info.last_sales_date"
            }
        },
        {"$sort": {"product_num": 1}}
    ]))

    # Compute flags like in dashboard
    cutoff_date_obj = datetime.strptime(cutoff_date, "%Y-%m-%d")
    for p in all_products:
        qty = p.get("quantity_on_hand", 0)
        sold = p.get("units_sold", 0)
        last_date_str = p.get("last_sales_date", "N/A")

        p["excess_qty"] = qty - sold
        p["is_excess"] = p["excess_qty"] > 0

        if last_date_str != "N/A":
            last_date_obj = datetime.strptime(last_date_str, "%Y-%m-%d")
            p["is_obsolete"] = last_date_obj < cutoff_date_obj
        else:
            p["is_obsolete"] = False

    # Paginate with 10 rows per page
    paginator = Paginator(all_products, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "reports/inventory_report.html", {
        "page_obj": page_obj,
    })

def add_product_stocks(request):
    if request.method == "POST":
        product_num = request.POST.get("product_num")
        add_stocks = int(request.POST.get("add_stocks", 0))
        if product_num and add_stocks > 0:
            inventory.update_one(
                {"product_num": product_num},
                {"$inc": {"quantity_on_hand": add_stocks}}
            )
    return render(request, "reports/add_stocks.html", {})