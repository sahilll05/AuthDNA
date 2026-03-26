import asyncio
import logging
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException
import sys
import os

# Add the backend directory to sys.path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_databases():
    client = Client()
    client.set_endpoint(settings.appwrite_endpoint)
    client.set_project(settings.appwrite_project_id)
    client.set_key(settings.appwrite_api_key)
    
    databases = Databases(client)
    db_id = settings.appwrite_database_id
    
    collections = [
        {
            "id": "hitl_decisions",
            "name": "HITL Decisions",
            "attributes": [
                {"key": "tenant_id", "type": "string", "size": 100, "required": True},
                {"key": "request_id", "type": "string", "size": 100, "required": True},
                {"key": "user_id", "type": "string", "size": 100, "required": True},
                {"key": "decision", "type": "string", "size": 20, "required": True},
                {"key": "timestamp", "type": "string", "size": 50, "required": True},
            ]
        }
    ]
    
    for coll in collections:
        try:
            logger.info(f"Checking collection: {coll['name']} ({coll['id']})...")
            try:
                databases.get_collection(db_id, coll['id'])
                logger.info(f"✅ Collection {coll['id']} already exists.")
            except AppwriteException:
                logger.info(f"Creating collection {coll['id']}...")
                databases.create_collection(db_id, coll['id'], coll['name'])
                
                # Add attributes
                for attr in coll['attributes']:
                    logger.info(f"  Adding attribute: {attr['key']}...")
                    if attr['type'] == "string":
                        databases.create_string_attribute(db_id, coll['id'], attr['key'], attr['size'], attr['required'])
                    elif attr['type'] == "integer":
                        databases.create_integer_attribute(db_id, coll['id'], attr['key'], attr['required'])
                    # Add more types if needed
                
                logger.info(f"✅ Collection {coll['id']} initialized.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize {coll['id']}: {e}")

if __name__ == "__main__":
    asyncio.run(init_databases())
