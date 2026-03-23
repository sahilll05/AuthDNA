# backend/config/__init__.py
from .firebase import get_firebase_app, get_firestore_db, tenant_collection, global_collection
from .settings import settings