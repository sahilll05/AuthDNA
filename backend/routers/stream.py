"""
SSE streaming endpoint — sends real-time login events to connected dashboard clients.
Each tenant gets its own asyncio.Queue. When evaluate fires, it pushes to the queue.
"""
import asyncio
import json
import logging
from typing import Dict, List
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from middleware.api_key_auth import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/stream", tags=["stream"])

# Global registry: tenant_id → list of queues (one per connected client)
_tenant_queues: Dict[str, List[asyncio.Queue]] = {}


def get_queues(tenant_id: str) -> List[asyncio.Queue]:
    return _tenant_queues.get(tenant_id, [])


def push_event(tenant_id: str, event_data: dict):
    """Called by evaluate router to broadcast a new login event to all SSE clients."""
    queues = _tenant_queues.get(tenant_id, [])
    dead = []
    for q in queues:
        try:
            q.put_nowait(event_data)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        queues.remove(q)


async def _event_generator(request: Request, tenant_id: str):
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    if tenant_id not in _tenant_queues:
        _tenant_queues[tenant_id] = []
    _tenant_queues[tenant_id].append(q)
    logger.info(f"📡 SSE client connected for tenant {tenant_id}")

    try:
        # Send a "connected" heartbeat immediately
        yield f"data: {json.dumps({'type': 'connected', 'tenant_id': tenant_id})}\n\n"

        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=15.0)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                # Heartbeat to keep the connection alive
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
    finally:
        if tenant_id in _tenant_queues:
            try:
                _tenant_queues[tenant_id].remove(q)
            except ValueError:
                pass
        logger.info(f"📡 SSE client disconnected for tenant {tenant_id}")


@router.get("/events")
async def stream_events(request: Request, tenant: dict = Depends(verify_api_key)):
    """
    Server-Sent Events endpoint. Connect with EventSource from the dashboard.
    Auth via X-API-Key header (same as all other endpoints).
    """
    tenant_id = tenant["tenant_id"]
    return StreamingResponse(
        _event_generator(request, tenant_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
