# backend/tests/test_phase11.py
"""
Phase 11 integration tests.
Run with: python -m pytest tests/test_phase11.py -v
"""
import pytest
import httpx
import asyncio

BASE_URL = "http://localhost:8000"
API_KEY = None
TENANT_ID = None


class TestPhase11:
    """Test the full multi-tenant flow"""

    @pytest.mark.asyncio
    async def test_01_health_check(self):
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            print("✅ Health check passed")

    @pytest.mark.asyncio
    async def test_02_register_tenant(self):
        global API_KEY, TENANT_ID

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/v1/tenants/register",
                json={
                    "company_name": "Test Corp",
                    "email": "test@testcorp.com",
                    "admin_secret": "admin-secret-change-me",
                    "tier": "free"
                }
            )
            assert resp.status_code == 200
            data = resp.json()
            API_KEY = data["api_key"]
            TENANT_ID = data["tenant_id"]
            assert API_KEY.startswith("sk_live_")
            print(f"✅ Tenant registered: {TENANT_ID}")
            print(f"   API Key: {API_KEY[:20]}...")

    @pytest.mark.asyncio
    async def test_03_evaluate_normal_login(self):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/v1/evaluate",
                headers={"X-API-Key": API_KEY},
                json={
                    "user_id": "alice@testcorp.com",
                    "ip": "49.36.128.100",  # India IP
                    "device_fp": "chrome-win-1920x1080",
                    "resource": "general",
                    "failed_attempts": 0
                }
            )
            assert resp.status_code == 200
            data = resp.json()
            print(f"✅ Normal login — Score: {data['score']}, "
                  f"Decision: {data['decision']}")
            print(f"   Explanation: {data['explanation']}")
            assert data["decision"] in ["ALLOW", "OTP"]

    @pytest.mark.asyncio
    async def test_04_evaluate_suspicious_login(self):
        async with httpx.AsyncClient() as client:
            # First, do a normal login to build DNA
            await client.post(
                f"{BASE_URL}/v1/evaluate",
                headers={"X-API-Key": API_KEY},
                json={
                    "user_id": "bob@testcorp.com",
                    "ip": "49.36.128.100",
                    "device_fp": "chrome-win-1920x1080",
                    "resource": "general",
                    "failed_attempts": 0
                }
            )

            # Now suspicious login — different everything
            resp = await client.post(
                f"{BASE_URL}/v1/evaluate",
                headers={"X-API-Key": API_KEY},
                json={
                    "user_id": "bob@testcorp.com",
                    "ip": "185.220.100.252",  # Tor exit node
                    "device_fp": "firefox-linux-1366x768",
                    "resource": "financial_data",
                    "failed_attempts": 5
                }
            )
            assert resp.status_code == 200
            data = resp.json()
            print(f"✅ Suspicious login — Score: {data['score']}, "
                  f"Decision: {data['decision']}")
            print(f"   Risk factors: {[f['factor'] for f in data['risk_factors']]}")
            assert data["score"] > 50

    @pytest.mark.asyncio
    async def test_05_dashboard_stats(self):
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/v1/dashboard/stats",
                headers={"X-API-Key": API_KEY}
            )
            assert resp.status_code == 200
            data = resp.json()
            print(f"✅ Dashboard stats — Total logins: {data['total_logins']}")

    @pytest.mark.asyncio
    async def test_06_get_logs(self):
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/v1/dashboard/logs?limit=10",
                headers={"X-API-Key": API_KEY}
            )
            assert resp.status_code == 200
            data = resp.json()
            print(f"✅ Login logs — Count: {len(data)}")

    @pytest.mark.asyncio
    async def test_07_usage(self):
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/v1/usage/current",
                headers={"X-API-Key": API_KEY}
            )
            assert resp.status_code == 200
            data = resp.json()
            print(f"✅ Usage — Calls this month: "
                  f"{data['total_calls_this_month']}")

    @pytest.mark.asyncio
    async def test_08_no_api_key(self):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/v1/evaluate",
                json={
                    "user_id": "hacker@evil.com",
                    "ip": "1.2.3.4",
                    "device_fp": "test",
                    "resource": "admin"
                }
            )
            assert resp.status_code == 401
            print("✅ Unauthenticated request properly rejected")

    @pytest.mark.asyncio
    async def test_09_invalid_api_key(self):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/v1/evaluate",
                headers={"X-API-Key": "sk_live_invalid_key_12345"},
                json={
                    "user_id": "hacker@evil.com",
                    "ip": "1.2.3.4",
                    "device_fp": "test",
                    "resource": "admin"
                }
            )
            assert resp.status_code == 401
            print("✅ Invalid API key properly rejected")

    @pytest.mark.asyncio
    async def test_10_tenant_isolation(self):
        """Verify that two tenants can't see each other's data"""
        async with httpx.AsyncClient() as client:
            # Register second tenant
            resp = await client.post(
                f"{BASE_URL}/v1/tenants/register",
                json={
                    "company_name": "Other Corp",
                    "email": "admin@othercorp.com",
                    "admin_secret": "admin-secret-change-me",
                    "tier": "free"
                }
            )
            other_key = resp.json()["api_key"]

            # Other tenant should see empty logs
            resp = await client.get(
                f"{BASE_URL}/v1/dashboard/logs",
                headers={"X-API-Key": other_key}
            )
            assert resp.status_code == 200
            assert len(resp.json()) == 0
            print("✅ Tenant isolation verified — Company B sees zero "
                  "logs from Company A")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])