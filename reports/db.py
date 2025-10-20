
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

uri = "mongodb+srv://kfgmationg_db_user:sevenzhiq@inventory-management.d9mq3xr.mongodb.net/?retryWrites=true&w=majority&appName=inventory-management"

client = MongoClient(uri, server_api=ServerApi('1'))
db = client["market"]   


inventory = db["inventory"]
sales = db["sales"]
