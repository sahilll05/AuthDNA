# backend/config/firebase.py
import firebase_admin
from firebase_admin import credentials, firestore
from config.settings import settings

_app = None
_db = None


def get_firebase_app():
    global _app
    if _app is None:
        cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
        _app = firebase_admin.initialize_app(cred, {
            "projectId": settings.FIREBASE_PROJECT_ID
        })
    return _app


def get_firestore_db():
    global _db
    if _db is None:
        get_firebase_app()
        _db = firestore.client()
    return _db


# ============================================================
# Multi-tenant collection helpers
# All data is isolated by tenant_id prefix
# ============================================================

def tenant_collection(tenant_id: str, collection_name: str):
    """
    Returns a Firestore collection reference scoped to a tenant.
    Structure: tenants/{tenant_id}/{collection_name}
    """
    db = get_firestore_db()
    return db.collection("tenants").document(tenant_id).collection(collection_name)


def global_collection(collection_name: str):
    """
    Returns a global (non-tenant) collection reference.
    Used for: api_keys, tenant_registry
    """
    db = get_firestore_db()
    return db.collection(collection_name)