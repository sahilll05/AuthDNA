# backend/middleware/tenant_context.py
"""
Tenant context manager — ensures data isolation.
Every database operation within a request uses the tenant_id
from the authenticated API key.
"""
from contextvars import ContextVar
from typing import Optional

# Context variable to hold current tenant_id across async calls
_current_tenant: ContextVar[Optional[str]] = ContextVar(
    "current_tenant", default=None
)


def set_tenant(tenant_id: str):
    """Set the current tenant for this request context"""
    _current_tenant.set(tenant_id)


def get_tenant() -> Optional[str]:
    """Get the current tenant for this request context"""
    return _current_tenant.get()


def require_tenant() -> str:
    """Get tenant or raise error if not set"""
    tenant_id = _current_tenant.get()
    if not tenant_id:
        raise RuntimeError("Tenant context not set. "
                           "Ensure API key middleware ran first.")
    return tenant_id