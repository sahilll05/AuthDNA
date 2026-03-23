# backend/test_firestore.py
"""
Run this to verify your Firestore connection works.
Usage: python test_firestore.py
"""
from config.firebase import get_firestore_db, tenant_collection, global_collection
from datetime import datetime


def test_firestore():
    print("🔥 Testing Firestore connection...\n")

    db = get_firestore_db()
    print("✅ Connected to Firestore!\n")

    # Test 1: Write to global collection
    print("📝 Test 1: Writing to tenant_registry...")
    test_ref = global_collection("tenant_registry").document("test_tenant_001")
    test_ref.set({
        "tenant_id": "test_tenant_001",
        "company_name": "Test Company",
        "email": "test@test.com",
        "tier": "free",
        "is_active": True,
        "created_at": datetime.utcnow().isoformat(),
        "total_api_calls": 0
    })
    print("   ✅ Written successfully!")

    # Test 2: Read it back
    print("\n📖 Test 2: Reading back...")
    doc = test_ref.get()
    if doc.exists:
        data = doc.to_dict()
        print(f"   ✅ Read back: {data['company_name']} ({data['tier']})")
    else:
        print("   ❌ Document not found!")

    # Test 3: Write to tenant-scoped collection
    print("\n📝 Test 3: Writing tenant-scoped data...")
    log_ref = tenant_collection("test_tenant_001", "login_logs")
    log_ref.add({
        "user_id": "testuser@test.com",
        "score": 15.5,
        "decision": "ALLOW",
        "timestamp": datetime.utcnow().isoformat()
    })
    print("   ✅ Login log written to tenants/test_tenant_001/login_logs/")

    # Test 4: Read tenant-scoped data
    print("\n📖 Test 4: Reading tenant-scoped data...")
    logs = tenant_collection("test_tenant_001", "login_logs").stream()
    count = 0
    for log in logs:
        count += 1
        data = log.to_dict()
        print(f"   ✅ Log: {data['user_id']} → {data['decision']} "
              f"(score: {data['score']})")
    print(f"   Total logs: {count}")

    # Test 5: Clean up test data
    print("\n🧹 Test 5: Cleaning up test data...")
    # Delete login logs
    logs = tenant_collection("test_tenant_001", "login_logs").stream()
    for log in logs:
        log.reference.delete()
    # Delete test tenant
    test_ref.delete()
    print("   ✅ Test data cleaned up!")

    print("\n" + "=" * 50)
    print("🎉 All Firestore tests passed!")
    print("=" * 50)
    print("\nYour Firestore is ready for Phase 11.")
    print("Now check Firebase Console to verify:")
    print(f"  https://console.firebase.google.com/project/"
          f"YOUR_PROJECT_ID/firestore")


if __name__ == "__main__":
    test_firestore()