# backend/services/tenant_service.py
from typing import Optional, List, Dict
from config.firebase import global_collection, tenant_collection
from datetime import datetime


class TenantService:
    """Manages tenant data with complete isolation"""

    @staticmethod
    async def get_tenant(tenant_id: str) -> Optional[Dict]:
        """Get tenant info by ID"""
        doc = global_collection("tenant_registry").document(tenant_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    @staticmethod
    async def update_tenant(tenant_id: str, updates: dict):
        """Update tenant fields"""
        global_collection("tenant_registry").document(tenant_id).update(updates)

    @staticmethod
    async def deactivate_tenant(tenant_id: str):
        """Soft-delete a tenant"""
        global_collection("tenant_registry").document(tenant_id).update({
            "is_active": False,
            "deactivated_at": datetime.utcnow().isoformat()
        })

    @staticmethod
    async def store_login_log(tenant_id: str, log_data: dict):
        """Store a login evaluation log for a tenant"""
        log_data["timestamp"] = datetime.utcnow().isoformat()
        tenant_collection(tenant_id, "login_logs").add(log_data)

    @staticmethod
    async def get_login_logs(
        tenant_id: str,
        limit: int = 50,
        user_id: str = None
    ) -> List[Dict]:
        """Get recent login logs for a tenant"""
        query = tenant_collection(tenant_id, "login_logs").order_by(
            "timestamp", direction="DESCENDING"
        ).limit(limit)

        if user_id:
            query = tenant_collection(tenant_id, "login_logs").where(
                "user_id", "==", user_id
            ).order_by("timestamp", direction="DESCENDING").limit(limit)

        docs = query.stream()
        return [doc.to_dict() for doc in docs]

    @staticmethod
    async def store_dna_profile(tenant_id: str, user_id: str, profile: dict):
        """Store/update behavioral DNA for a user within a tenant"""
        profile["updated_at"] = datetime.utcnow().isoformat()
        tenant_collection(tenant_id, "dna_profiles").document(user_id).set(
            profile, merge=True
        )

    @staticmethod
    async def get_dna_profile(tenant_id: str, user_id: str) -> Optional[Dict]:
        """Get behavioral DNA profile for a specific user in a tenant"""
        doc = tenant_collection(tenant_id, "dna_profiles").document(user_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    @staticmethod
    async def get_all_dna_profiles(tenant_id: str) -> List[Dict]:
        """Get all DNA profiles for a tenant"""
        docs = tenant_collection(tenant_id, "dna_profiles").stream()
        return [{"user_id": doc.id, **doc.to_dict()} for doc in docs]

    @staticmethod
    async def increment_api_calls(tenant_id: str):
        """Increment total API call counter for tenant"""
        from google.cloud.firestore_v1 import Increment
        global_collection("tenant_registry").document(tenant_id).update({
            "total_api_calls": Increment(1)
        })