import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, List

from appwrite.id import ID
from appwrite.query import Query
from appwrite.exception import AppwriteException

from config.appwrite_client import get_databases
from config.settings import settings

logger = logging.getLogger(__name__)
DB_ID = settings.appwrite_database_id


def _sid(raw: str) -> str:
    """Make any string into a valid Appwrite doc ID (max 36 chars, alphanumeric)."""
    if len(raw) > 36:
        result = hashlib.md5(raw.encode()).hexdigest()
        logger.info(f"   ⚙️  _sid() transformed {raw[:16]}...(len={len(raw)}) → {result}(len={len(result)})")
        return result
    clean = ""
    for c in raw:
        if c.isalnum() or c in ("-", "_", "."):
            clean += c
        else:
            clean += "_"
    if clean and not clean[0].isalnum():
        clean = "d" + clean
    result = clean[:36]
    logger.info(f"   ⚙️  _sid() cleaned {raw[:16]}...(len={len(raw)}) → {result}(len={len(result)})")
    return result


class DatabaseService:
    def __init__(self):
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_databases()
        return self._db

    # === TENANTS ===
    async def create_tenant(self, tenant_id: str, data: dict):
        db = get_databases()
        return await asyncio.to_thread(db.create_document, DB_ID, "tenants", _sid(tenant_id), data)

    async def get_tenant(self, tenant_id: str):
        try:
            db = get_databases()
            return await asyncio.to_thread(db.get_document, DB_ID, "tenants", _sid(tenant_id))
        except AppwriteException:
            return None

    async def update_tenant(self, tenant_id: str, data: dict):
        db = get_databases()
        return await asyncio.to_thread(db.update_document, DB_ID, "tenants", _sid(tenant_id), data)

    # === API KEYS ===
    async def save_api_key(self, key_hash: str, data: dict):
        did = _sid(key_hash)
        logger.info(f"💾 Saving API key - original_hash: {key_hash[:16]}... → doc_id: {did}")
        # Use fresh database instance each time to avoid state issues
        db = get_databases()
        return await asyncio.to_thread(db.create_document, DB_ID, "api_keys", did, data)

    async def get_api_key(self, key_hash: str):
        did = _sid(key_hash)
        logger.info(f"🔍 Looking up API key - original_hash: {key_hash[:16]}... → doc_id: {did}")
        try:
            # Use fresh database instance each time to avoid state issues
            db = get_databases()
            result = await asyncio.to_thread(db.get_document, DB_ID, "api_keys", did)
            logger.info(f"✅ Found API key document: {result.get('key_prefix')}")
            return result
        except AppwriteException as e:
            logger.error(f"❌ API key not found: {e}")
            return None

    async def update_api_key(self, key_hash: str, data: dict):
        did = _sid(key_hash)
        db = get_databases()
        return await asyncio.to_thread(db.update_document, DB_ID, "api_keys", did, data)

    async def revoke_tenant_keys(self, tenant_id: str):
        try:
            db = get_databases()
            result = await asyncio.to_thread(db.list_documents, DB_ID, "api_keys",
                [Query.equal("tenant_id", tenant_id), Query.equal("status", "active")]
            )
            for doc in result.get("documents", []):
                await asyncio.to_thread(db.update_document, DB_ID, "api_keys", doc["$id"],
                    {"status": "revoked"}
                )
        except AppwriteException as e:
            logger.error(f"Revoke error: {e}")

    # === LOGIN LOGS ===
    async def save_login_log(self, tenant_id: str, data: dict):
        data["tenant_id"] = tenant_id
        db = get_databases()
        return await asyncio.to_thread(db.create_document, DB_ID, "login_logs", ID.unique(), data)

    async def update_login_log_decision(self, tenant_id: str, request_id: str, decision: str):
        try:
            db = get_databases()
            # Find the document ID first
            q = [Query.equal("tenant_id", tenant_id), Query.equal("request_id", request_id), Query.limit(1)]
            r = await asyncio.to_thread(db.list_documents, DB_ID, "login_logs", q)
            docs = r.get("documents", [])
            if docs:
                did = docs[0]["$id"]
                await asyncio.to_thread(db.update_document, DB_ID, "login_logs", did, {"decision": decision})
                return True
            return False
        except AppwriteException as e:
            logger.error(f"Failed to update log decision: {e}")
            return False

    async def get_login_logs(self, tenant_id: str, limit=50, user_id=None):
        q = [Query.equal("tenant_id", tenant_id), Query.order_desc("timestamp"), Query.limit(limit)]
        if user_id:
            q.append(Query.equal("user_id", user_id))
        try:
            db = get_databases()
            r = await asyncio.to_thread(db.list_documents, DB_ID, "login_logs", q)
            return r.get("documents", [])
        except AppwriteException:
            return []


    # === HITL DECISIONS ===

    async def save_hitl_decision(self, tenant_id: str, request_id: str, user_id: str, decision: str):
        data = {
            "tenant_id": tenant_id,
            "request_id": request_id,
            "user_id": user_id,
            "decision": decision,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        db = get_databases()
        return await asyncio.to_thread(db.create_document, DB_ID, "hitl_decisions", ID.unique(), data)

    async def get_recent_hitl_trust(self, tenant_id: str, user_id: str) -> bool:
        """Check if an admin has recently (last 1h) approved this user via HITL."""
        from datetime import timedelta
        # Simple implementation: check if any 'ALLOW' decision exists for this user in last hour
        since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        q = [
            Query.equal("tenant_id", tenant_id),
            Query.equal("user_id", user_id),
            Query.equal("decision", "ALLOW"),
            Query.greater_than("timestamp", since),
            Query.limit(1)
        ]
        try:
            db = get_databases()
            r = await asyncio.to_thread(db.list_documents, DB_ID, "hitl_decisions", q)
            return len(r.get("documents", [])) > 0
        except AppwriteException:
            return False

    # === DNA PROFILES ===
    async def get_dna_profile(self, tenant_id: str, user_id: str):
        did = hashlib.md5(f"{tenant_id}_{user_id}".encode()).hexdigest()
        try:
            db = get_databases()
            return await asyncio.to_thread(db.get_document, DB_ID, "dna_profiles", did)
        except AppwriteException:
            return None

    async def save_dna_profile(self, tenant_id: str, user_id: str, data: dict):
        did = hashlib.md5(f"{tenant_id}_{user_id}".encode()).hexdigest()
        data["tenant_id"] = tenant_id
        data["user_id"] = user_id
        try:
            db = get_databases()
            return await asyncio.to_thread(db.update_document, DB_ID, "dna_profiles", did, data)
        except AppwriteException:
            db = get_databases()
            return await asyncio.to_thread(db.create_document, DB_ID, "dna_profiles", did, data)

    async def get_all_dna_profiles(self, tenant_id: str):
        try:
            db = get_databases()
            r = await asyncio.to_thread(db.list_documents, DB_ID, "dna_profiles",
                [Query.equal("tenant_id", tenant_id), Query.limit(100)]
            )
            return r.get("documents", [])
        except AppwriteException:
            return []

    # === USAGE ===
    async def increment_usage(self, tenant_id: str, decision: str, latency_ms: float, score: float):
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        did = hashlib.md5(f"{tenant_id}_{period}".encode()).hexdigest()
        try:
            db = get_databases()
            doc = await asyncio.to_thread(db.get_document, DB_ID, "usage", did)
            total = doc.get("total_calls", 0)
            await asyncio.to_thread(db.update_document, DB_ID, "usage", did, {
                "total_calls": total + 1,
                f"{decision.lower()}_count": doc.get(f"{decision.lower()}_count", 0) + 1,
                "avg_latency_ms": round((doc.get("avg_latency_ms", 0) * total + latency_ms) / (total + 1), 1),
                "avg_score": round((doc.get("avg_score", 0) * total + score) / (total + 1), 1),
            })
        except AppwriteException:
            db = get_databases()
            await asyncio.to_thread(db.create_document, DB_ID, "usage", did, {
                "tenant_id": tenant_id, "period": period, "total_calls": 1,
                "allow_count": 1 if decision == "ALLOW" else 0,
                "block_count": 1 if decision == "BLOCK" else 0,
                "otp_count": 1 if decision == "OTP" else 0,
                "stepup_count": 1 if decision == "STEPUP" else 0,
                "avg_latency_ms": round(latency_ms, 1),
                "avg_score": round(score, 1),
            })

    async def get_usage(self, tenant_id: str):
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        did = hashlib.md5(f"{tenant_id}_{period}".encode()).hexdigest()
        try:
            db = get_databases()
            return await asyncio.to_thread(db.get_document, DB_ID, "usage", did)
        except AppwriteException:
            return None

    async def get_usage_history(self, tenant_id: str):
        try:
            db = get_databases()
            r = await asyncio.to_thread(db.list_documents, DB_ID, "usage",
                [Query.equal("tenant_id", tenant_id), Query.order_desc("period"), Query.limit(6)])
            return r.get("documents", [])
        except AppwriteException:
            return []

    # === RATE TRACKING ===
    async def check_and_increment_rate(self, tenant_id: str) -> int:
        hk = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
        did = hashlib.md5(f"{tenant_id}_{hk}".encode()).hexdigest()
        try:
            db = get_databases()
            doc = await asyncio.to_thread(db.get_document, DB_ID, "rate_tracking", did)
            n = doc.get("count", 0) + 1
            await asyncio.to_thread(db.update_document, DB_ID, "rate_tracking", did, {"count": n})
            return n
        except AppwriteException:
            db = get_databases()
            await asyncio.to_thread(db.create_document, DB_ID, "rate_tracking", did,
                {"tenant_id": tenant_id, "hour_key": hk, "count": 1})
            return 1

    async def get_current_rate(self, tenant_id: str) -> int:
        hk = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
        did = hashlib.md5(f"{tenant_id}_{hk}".encode()).hexdigest()
        try:
            doc = await asyncio.to_thread(self.db.get_document, DB_ID, "rate_tracking", did)
            return doc.get("count", 0)
        except AppwriteException:
            return 0


db_service = DatabaseService()