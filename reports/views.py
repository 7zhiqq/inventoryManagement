from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from datetime import datetime, timedelta
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
import csv
import json

uri = "mongodb+srv://kfgmationg_db_user:sevenzhiq@inventory-management.d9mq3xr.mongodb.net/?retryWrites=true&w=majority&appName=inventory-management"

client = MongoClient(uri, server_api=ServerApi('1'))

db = client["market"]
inventory = db["inventory"]
sales = db["sales"]

def get_processed_products():
    """Helper function to get and process all products"""
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
        {"$unwind": {"path": "$sales_info", "preserveNullAndEmptyArrays": True}},
        {
            "$project": {
                "_id": 0,
                "product_num": 1,
                "item_name": 1,
                "quantity_on_hand": 1,
                "units_sold": {"$ifNull": ["$sales_info.units_sold", 0]},
                "last_sales_date": {"$ifNull": ["$sales_info.last_sales_date", "N/A"]}
            }
        },
        {"$sort": {"product_num": 1}}
    ]))

    cutoff_date_obj = datetime.strptime(cutoff_date, "%Y-%m-%d")
    for p in all_products:
        qty = p.get("quantity_on_hand", 0)
        sold = p.get("units_sold", 0)
        last_date_str = p.get("last_sales_date", "N/A")

        p["excess_qty"] = qty - sold
        p["is_excess"] = p["excess_qty"] > 0

        if last_date_str != "N/A":
            try:
                last_date_obj = datetime.strptime(last_date_str, "%Y-%m-%d")
                p["is_obsolete"] = last_date_obj < cutoff_date_obj
            except:
                p["is_obsolete"] = False
        else:
            p["is_obsolete"] = False

    return all_products

def dashboard(request):
    all_products = get_processed_products()
    return render(request, "reports/dashboard.html", {
        "products": all_products,
    })

def excess_inventory(request):
    all_products = get_processed_products()
    excess_items = [p for p in all_products if p["is_excess"]]
    
    return render(request, "reports/excess.html", {
        "products": excess_items,
    })

def obsolete_inventory(request):
    all_products = get_processed_products()
    obsolete_products = [p for p in all_products if p["is_obsolete"]]

    return render(request, "reports/obsolete.html", {
        "products": obsolete_products
    })

def inventory_report(request):
    all_products = get_processed_products()
    
    paginator = Paginator(all_products, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "reports/inventory_report.html", {
        "page_obj": page_obj,
    })

@require_http_methods(["POST"])
def add_product(request):
    """Add a new product to inventory"""
    try:
        product_num = request.POST.get("product_num")
        item_name = request.POST.get("item_name")
        quantity = int(request.POST.get("quantity", 0))
        
        if not product_num or not item_name:
            return JsonResponse({"success": False, "message": "Product number and name are required"})
        
        # Check if product exists
        existing = inventory.find_one({"product_num": product_num})
        if existing:
            return JsonResponse({"success": False, "message": "Product already exists"})
        
        inventory.insert_one({
            "product_num": product_num,
            "item_name": item_name,
            "quantity_on_hand": quantity
        })
        
        return JsonResponse({"success": True, "message": "Product added successfully"})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})

@require_http_methods(["POST"])
def add_stock(request):
    """Add stock to existing product"""
    try:
        product_num = request.POST.get("product_num")
        add_quantity = int(request.POST.get("quantity", 0))
        
        if not product_num or add_quantity <= 0:
            return JsonResponse({"success": False, "message": "Valid product number and quantity required"})
        
        result = inventory.update_one(
            {"product_num": product_num},
            {"$inc": {"quantity_on_hand": add_quantity}}
        )
        
        if result.modified_count > 0:
            return JsonResponse({"success": True, "message": f"Added {add_quantity} units to stock"})
        else:
            return JsonResponse({"success": False, "message": "Product not found"})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})

@require_http_methods(["POST"])
def add_sale(request):
    """Add a new sale record"""
    try:
        product_num = request.POST.get("product_num")
        units_sold = int(request.POST.get("units_sold", 0))
        sale_date = request.POST.get("sale_date", datetime.now().strftime("%Y-%m-%d"))
        
        if not product_num or units_sold <= 0:
            return JsonResponse({"success": False, "message": "Valid product number and units sold required"})
        
        # Check if product exists
        product = inventory.find_one({"product_num": product_num})
        if not product:
            return JsonResponse({"success": False, "message": "Product not found"})
        
        # Check if enough stock
        if product.get("quantity_on_hand", 0) < units_sold:
            return JsonResponse({"success": False, "message": "Insufficient stock"})
        
        # Update or create sales record
        sales.update_one(
            {"product_num": product_num},
            {
                "$set": {
                    "last_sales_date": sale_date
                },
                "$inc": {
                    "units_sold": units_sold
                }
            },
            upsert=True
        )
        
        # Reduce inventory
        inventory.update_one(
            {"product_num": product_num},
            {"$inc": {"quantity_on_hand": -units_sold}}
        )
        
        return JsonResponse({"success": True, "message": f"Sale recorded: {units_sold} units"})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})

@require_http_methods(["POST"])
def edit_product(request):
    """Edit product details"""
    try:
        product_num = request.POST.get("product_num")
        item_name = request.POST.get("item_name")
        quantity = int(request.POST.get("quantity", 0))
        
        if not product_num:
            return JsonResponse({"success": False, "message": "Product number required"})
        
        update_data = {}
        if item_name:
            update_data["item_name"] = item_name
        if quantity >= 0:
            update_data["quantity_on_hand"] = quantity
        
        result = inventory.update_one(
            {"product_num": product_num},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            return JsonResponse({"success": True, "message": "Product updated successfully"})
        else:
            return JsonResponse({"success": False, "message": "Product not found or no changes made"})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})

@require_http_methods(["POST"])
def delete_product(request):
    """Delete a product"""
    try:
        product_num = request.POST.get("product_num")
        
        if not product_num:
            return JsonResponse({"success": False, "message": "Product number required"})
        
        inventory.delete_one({"product_num": product_num})
        sales.delete_one({"product_num": product_num})
        
        return JsonResponse({"success": True, "message": "Product deleted successfully"})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})

def download_csv(request):
    """Download selected products as CSV"""
    try:
        product_nums = request.GET.get("products", "").split(",")
        product_nums = [p.strip() for p in product_nums if p.strip()]
        
        if not product_nums:
            all_products = get_processed_products()
        else:
            all_products = get_processed_products()
            all_products = [p for p in all_products if p["product_num"] in product_nums]
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="inventory_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Product #', 'Item Name', 'Quantity on Hand', 'Units Sold', 'Last Sales Date', 'Excess Qty', 'Is Excess', 'Is Obsolete'])
        
        for p in all_products:
            writer.writerow([
                p['product_num'],
                p['item_name'],
                p['quantity_on_hand'],
                p['units_sold'],
                p['last_sales_date'],
                p['excess_qty'],
                'Yes' if p['is_excess'] else 'No',
                'Yes' if p['is_obsolete'] else 'No'
            ])
        
        return response
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)

def get_product_details(request, product_num):
    """Get product details for editing"""
    try:
        product = inventory.find_one({"product_num": product_num}, {"_id": 0})
        if product:
            return JsonResponse({"success": True, "product": product})
        else:
            return JsonResponse({"success": False, "message": "Product not found"})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})