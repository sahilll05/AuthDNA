# backend/utils/hashing.py
import hashlib
import secrets
from config.settings import settings


def generate_api_key(tenant_id: str) -> str:
    """
    Generate a unique API key for a tenant.
    Format: sk_live_{random_hex}_{tenant_slug}
    """
    random_part = secrets.token_hex(16)
    # Create a short slug from tenant_id
    slug = tenant_id[:8]
    return f"{settings.API_KEY_PREFIX}{random_part}_{slug}"


def hash_api_key(api_key: str) -> str:
    """
    Hash the API key for storage. We store hashed, compare hashed.
    Using SHA-256 for fast lookups (API keys have high entropy).
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def generate_tenant_id(company_name: str) -> str:
    """
    Generate a unique tenant ID from company name.
    """
    slug = company_name.lower().replace(" ", "_").replace("-", "_")
    # Remove special chars
    slug = "".join(c for c in slug if c.isalnum() or c == "_")
    random_suffix = secrets.token_hex(4)
    return f"{slug}_{random_suffix}"


def generate_request_id() -> str:
    """Generate unique request ID"""
    return f"req_{secrets.token_hex(8)}"