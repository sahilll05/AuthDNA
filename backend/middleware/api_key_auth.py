import hashlib
import logging
from datetime import datetime, timezone
from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyHeader
from services.database_service import db_service

logger = logging.getLogger(__name__)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(request: Request, api_key: str = Depends(api_key_header)):
    # Fallback to query parameter if header is missing (useful for SSE/WebSockets)
    if not api_key:
        api_key = request.query_params.get("api_key")

    if not api_key:
        logger.error("❌ Missing X-API-Key header or query parameter in request")
        logger.error(f"   Headers received: {dict(request.headers)}")
        raise HTTPException(401, "Missing API key")


    logger.info(f"🔐 Verifying API key: {api_key[:20]}... (len={len(api_key)})")
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    logger.info(f"   Hash computed: {key_hash[:16]}... (len={len(key_hash)})")
    key_doc = await db_service.get_api_key(key_hash)
    if not key_doc:
        logger.error(f"❌ API key not found in database. Hash: {key_hash[:16]}...")
        raise HTTPException(401, "Invalid API key")
    logger.info(f"✅ API key found: {key_doc.get('key_prefix')}...")
    if key_doc.get("status") != "active":
        logger.error(f"❌ API key revoked: {key_doc.get('key_prefix')}")
        raise HTTPException(401, "API key revoked")

    tenant_id = key_doc["tenant_id"]
    tenant = await db_service.get_tenant(tenant_id)
    if not tenant or not tenant.get("is_active", True):
        raise HTTPException(401, "Tenant inactive")

    info = {
        "tenant_id": tenant_id,
        "company_name": tenant.get("company_name", ""),
        "email": tenant.get("email", ""),
        "tier": key_doc.get("tier", "free"),
        "webhook_url": tenant.get("webhook_url"),
        "key_hash": key_hash,
        "key_prefix": key_doc.get("key_prefix", ""),
    }
    request.state.tenant = info

    try:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        await db_service.update_api_key(key_hash, {"last_used": ts})
    except Exception:
        pass

    return info