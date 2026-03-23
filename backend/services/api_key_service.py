# backend/services/api_key_service.py
from typing import Optional, Tuple
from config.firebase import global_collection, get_firestore_db
from utils.hashing import generate_api_key, hash_api_key, generate_tenant_id
from config.settings import settings
from datetime import datetime


class APIKeyService:
    """Manages API key lifecycle — create, validate, revoke, rotate"""

    @staticmethod
    async def create_key(
        company_name: str,
        email: str,
        tier: str = "free",
        webhook_url: str = None
    ) -> Tuple[str, str]:
        """
        Create a new tenant with an API key.
        Returns: (tenant_id, raw_api_key)
        The raw key is returned only ONCE at creation time.
        """
        tenant_id = generate_tenant_id(company_name)
        raw_key = generate_api_key(tenant_id)
        hashed_key = hash_api_key(raw_key)

        # Store tenant info
        tenant_ref = global_collection("tenant_registry").document(tenant_id)
        tenant_ref.set({
            "tenant_id": tenant_id,
            "company_name": company_name,
            "email": email,
            "tier": tier,
            "is_active": True,
            "created_at": datetime.utcnow().isoformat(),
            "webhook_url": webhook_url,
            "total_api_calls": 0
        })

        # Store hashed API key → tenant mapping
        key_ref = global_collection("api_keys").document(hashed_key)
        key_ref.set({
            "tenant_id": tenant_id,
            "hashed_key": hashed_key,
            "tier": tier,
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "last_used": None
        })

        return tenant_id, raw_key

    @staticmethod
    async def validate_key(raw_key: str) -> Optional[dict]:
        """
        Validate an API key and return tenant info.
        Returns None if invalid/revoked.
        """
        if not raw_key or not raw_key.startswith(settings.API_KEY_PREFIX):
            return None

        hashed = hash_api_key(raw_key)
        key_ref = global_collection("api_keys").document(hashed)
        key_doc = key_ref.get()

        if not key_doc.exists:
            return None

        key_data = key_doc.to_dict()

        if key_data.get("status") != "active":
            return None

        tenant_id = key_data["tenant_id"]

        # Get tenant info
        tenant_ref = global_collection("tenant_registry").document(tenant_id)
        tenant_doc = tenant_ref.get()

        if not tenant_doc.exists:
            return None

        tenant_data = tenant_doc.to_dict()

        if not tenant_data.get("is_active", False):
            return None

        # Update last_used timestamp
        key_ref.update({"last_used": datetime.utcnow().isoformat()})

        return {
            "tenant_id": tenant_id,
            "company_name": tenant_data["company_name"],
            "email": tenant_data["email"],
            "tier": tenant_data.get("tier", "free"),
            "webhook_url": tenant_data.get("webhook_url"),
            "is_active": True
        }

    @staticmethod
    async def rotate_key(tenant_id: str) -> str:
        """
        Revoke existing key and create a new one.
        Returns the new raw key.
        """
        db = get_firestore_db()

        # Find and revoke existing key(s) for this tenant
        existing_keys = global_collection("api_keys").where(
            "tenant_id", "==", tenant_id
        ).where("status", "==", "active").stream()

        for key_doc in existing_keys:
            key_doc.reference.update({
                "status": "revoked",
                "revoked_at": datetime.utcnow().isoformat()
            })

        # Generate new key
        new_raw_key = generate_api_key(tenant_id)
        new_hashed = hash_api_key(new_raw_key)

        # Get tenant tier
        tenant_doc = global_collection("tenant_registry").document(tenant_id).get()
        tier = tenant_doc.to_dict().get("tier", "free") if tenant_doc.exists else "free"

        # Store new key
        global_collection("api_keys").document(new_hashed).set({
            "tenant_id": tenant_id,
            "hashed_key": new_hashed,
            "tier": tier,
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "last_used": None
        })

        return new_raw_key

    @staticmethod
    async def revoke_key(tenant_id: str):
        """Revoke all active keys for a tenant"""
        existing_keys = global_collection("api_keys").where(
            "tenant_id", "==", tenant_id
        ).where("status", "==", "active").stream()

        for key_doc in existing_keys:
            key_doc.reference.update({
                "status": "revoked",
                "revoked_at": datetime.utcnow().isoformat()
            })