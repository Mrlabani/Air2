from pymongo import MongoClient
import os

MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["torrentBot"]
downloads = db["downloads"]

def add_download(data):
    downloads.insert_one(data)

def get_all_downloads():
    return list(downloads.find({}).sort("timestamp", -1))

def clear_downloads():
    downloads.delete_many({})
