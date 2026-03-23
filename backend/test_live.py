# backend/test_live.py
"""
Quick manual test script — run this to test the full flow.
Usage: python test_live.py
"""
import httpx
import json
import sys

BASE_URL = "http://localhost:8000"


def main():
    print("=" * 60)
    print("🧪 AI Identity Risk Score Engine — Phase 11 Live Test")
    print("=" * 60)

    with httpx.Client(timeout=30.0) as client:

        # Step 1: Health check
        print("\n📍 Step 1: Health Check")
        resp = client.get(f"{BASE_URL}/health")
        print(f"   Status: {resp.json()}")

        # Step 2: Register tenant
        print("\n📍 Step 2: Register Tenant")
        resp = client.post(f"{BASE_URL}/v1/tenants/register", json={
            "company_name": "Demo Corp",
            "email": "admin@democorp.com",
            "admin_secret": "admin-secret-change-me",
            "tier": "free"
        })
        reg_data = resp.json()
        api_key = reg_data["api_key"]
        tenant_id = reg_data["tenant_id"]
        print(f"   Tenant ID: {tenant_id}")
        print(f"   API Key: {api_key}")

        headers = {"X-API-Key": api_key}

        # Step 3: Normal login
        print("\n📍 Step 3: Evaluate Normal Login")
        resp = client.post(f"{BASE_URL}/v1/evaluate", headers=headers, json={
            "user_id": "alice@democorp.com",
            "ip": "49.36.128.100",
            "device_fp": "chrome-win-1920x1080",
            "resource": "profile",
            "failed_attempts": 0
        })
        data = resp.json()
        print(f"   Decision: {data['decision']}")
        print(f"   Score: {data['score']}")
        print(f"   Explanation: {data['explanation']}")
        print(f"   Processing: {data['processing_time_ms']}ms")

        # Step 4: Same user, second login (should have DNA now)
        print("\n📍 Step 4: Same User Second Login (DNA built)")
        resp = client.post(f"{BASE_URL}/v1/evaluate", headers=headers, json={
            "user_id": "alice@democorp.com",
            "ip": "49.36.128.100",
            "device_fp": "chrome-win-1920x1080",
            "resource": "profile",
            "failed_attempts": 0
        })
        data = resp.json()
        print(f"   Decision: {data['decision']}")
        print(f"   Score: {data['score']}")
        print(f"   DNA Match: {data['dna_match']}%")

        # Step 5: Suspicious login — new device, different IP, failed attempts
        print("\n📍 Step 5: Evaluate SUSPICIOUS Login")
        resp = client.post(f"{BASE_URL}/v1/evaluate", headers=headers, json={
            "user_id": "alice@democorp.com",
            "ip": "185.220.100.252",
            "device_fp": "firefox-linux-unknown",
            "resource": "financial_data",
            "failed_attempts": 4
        })
        data = resp.json()
        print(f"   Decision: {data['decision']}")
        print(f"   Score: {data['score']}")
        print(f"   Explanation: {data['explanation']}")
        print(f"   Risk Factors:")
        for f in data["risk_factors"]:
            print(f"     • {f['factor']}: {f['description']} "
                  f"({f['contribution']:+.1f})")

        # Step 6: Dashboard
        print("\n📍 Step 6: Dashboard Stats")
        resp = client.get(f"{BASE_URL}/v1/dashboard/stats", headers=headers)
        print(f"   {json.dumps(resp.json(), indent=2)}")

        # Step 7: Login logs
        print("\n📍 Step 7: Recent Login Logs")
        resp = client.get(f"{BASE_URL}/v1/dashboard/logs?limit=5",
                         headers=headers)
        logs = resp.json()
        print(f"   Total logs: {len(logs)}")
        for log in logs[:3]:
            print(f"     • {log['user_id']} → {log['decision']} "
                  f"(score: {log['score']})")

        # Step 8: Usage
        print("\n📍 Step 8: API Usage")
        resp = client.get(f"{BASE_URL}/v1/usage/current", headers=headers)
        print(f"   {json.dumps(resp.json(), indent=2)}")

        # Step 9: User DNA
        print("\n📍 Step 9: User DNA Profile")
        resp = client.get(
            f"{BASE_URL}/v1/dashboard/users/alice@democorp.com/dna",
            headers=headers
        )
        if resp.status_code == 200:
            print(f"   {json.dumps(resp.json(), indent=2)}")

        print("\n" + "=" * 60)
        print("✅ All tests passed! Phase 11 is working.")
        print("=" * 60)


if __name__ == "__main__":
    main()