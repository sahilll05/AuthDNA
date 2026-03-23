# backend/services/webhook_service.py
import aiohttp
import asyncio
from typing import Dict, Optional
from config.settings import settings
from datetime import datetime
import json


class WebhookService:
    """Delivers webhook events to tenant-registered URLs"""

    @staticmethod
    async def send_webhook(
        webhook_url: str,
        tenant_id: str,
        event_type: str,
        payload: Dict
    ) -> bool:
        """
        Send a webhook POST to the tenant's registered URL.
        Retries up to WEBHOOK_RETRY_COUNT times.
        
        event_type: "risk.block", "risk.stepup", "risk.otp"
        """
        if not webhook_url:
            return False

        webhook_body = {
            "event": event_type,
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload
        }

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event_type,
            "X-Tenant-ID": tenant_id
        }

        for attempt in range(settings.WEBHOOK_RETRY_COUNT):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        webhook_url,
                        json=webhook_body,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(
                            total=settings.WEBHOOK_TIMEOUT
                        )
                    ) as resp:
                        if resp.status in (200, 201, 202, 204):
                            print(f"Webhook delivered to {webhook_url} "
                                  f"(attempt {attempt + 1})")
                            return True
                        else:
                            print(f"Webhook failed with status {resp.status} "
                                  f"(attempt {attempt + 1})")

            except asyncio.TimeoutError:
                print(f"Webhook timeout to {webhook_url} "
                      f"(attempt {attempt + 1})")
            except Exception as e:
                print(f"Webhook error: {e} (attempt {attempt + 1})")

            # Wait before retry (exponential backoff)
            if attempt < settings.WEBHOOK_RETRY_COUNT - 1:
                await asyncio.sleep(2 ** attempt)

        print(f"Webhook delivery FAILED after {settings.WEBHOOK_RETRY_COUNT} "
              f"attempts to {webhook_url}")
        return False

    @staticmethod
    async def fire_and_forget(
        webhook_url: str,
        tenant_id: str,
        event_type: str,
        payload: Dict
    ):
        """
        Non-blocking webhook delivery.
        Don't await this — it runs in the background.
        """
        asyncio.create_task(
            WebhookService.send_webhook(
                webhook_url, tenant_id, event_type, payload
            )
        )