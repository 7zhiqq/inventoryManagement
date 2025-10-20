# inventory_mgmt/db.py
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

uri = "mongodb+srv://kfgmationg_db_user:sevenzhiq@inventory-management.d9mq3xr.mongodb.net/?retryWrites=true&w=majority&appName=inventory-management"

client = MongoClient(uri, server_api=ServerApi('1'))
db = client["market"]   # your database name

# Example collections
inventory = db["inventory"]
sales = db["sales"]
