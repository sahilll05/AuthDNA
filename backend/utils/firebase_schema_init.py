import os
import sys
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Initialize Firebase (same as main.py)
firebase_config_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "config",
    "firebase_service_account.json"
)

if not os.path.exists(firebase_config_path):
    print(f"❌ Firebase config not found at {firebase_config_path}")
    sys.exit(1)

try:
    creds = credentials.Certificate(firebase_config_path)
    firebase_admin.initialize_app(creds)
    db = firestore.client()
    print("✅ Firebase initialized successfully")
except ValueError as e:
    # App already initialized
    db = firestore.client()
    print("✅ Firebase already initialized")
except Exception as e:
    print(f"❌ Firebase initialization error: {e}")
    sys.exit(1)

# ============ ROLE DEFINITIONS ============
ROLES = {
    "admin": {"permissions": ["read", "write", "delete", "approve"], "level": 5},
    "manager": {"permissions": ["read", "write", "approve"], "level": 4},
    "developer": {"permissions": ["read", "write"], "level": 3},
    "analyst": {"permissions": ["read"], "level": 2},
    "viewer": {"permissions": ["read"], "level": 1}
}

# ============ RESOURCES ============
RESOURCES = [
    {"id": "resource_001", "name": "User Database", "sensitivity": 5, "owner": "admin"},
    {"id": "resource_002", "name": "API Keys", "sensitivity": 5, "owner": "admin"},
    {"id": "resource_003", "name": "Logs", "sensitivity": 3, "owner": "analyst"},
    {"id": "resource_004", "name": "Reports", "sensitivity": 2, "owner": "analyst"},
    {"id": "resource_005", "name": "Configuration", "sensitivity": 4, "owner": "manager"},
    {"id": "resource_006", "name": "Documentation", "sensitivity": 1, "owner": "viewer"},
    {"id": "resource_007", "name": "Code Repository", "sensitivity": 4, "owner": "developer"},
    {"id": "resource_008", "name": "Backups", "sensitivity": 5, "owner": "admin"},
    {"id": "resource_009", "name": "Monitoring", "sensitivity": 3, "owner": "analyst"},
    {"id": "resource_010", "name": "Security Policies", "sensitivity": 5, "owner": "admin"}
]

# ============ SAMPLE USERS ============
SAMPLE_USERS = [
    {
        "user_id": "u_admin_001",
        "email": "alice@company.com",
        "name": "Alice Admin",
        "role": "admin",
        "created_at": datetime.now().isoformat(),
        "last_login": None,
        "is_active": True
    },
    {
        "user_id": "u_dev_001",
        "email": "bob@company.com",
        "name": "Bob Developer",
        "role": "developer",
        "created_at": datetime.now().isoformat(),
        "last_login": None,
        "is_active": True
    },
    {
        "user_id": "u_viewer_001",
        "email": "charlie@company.com",
        "name": "Charlie Viewer",
        "role": "viewer",
        "created_at": datetime.now().isoformat(),
        "last_login": None,
        "is_active": True
    }
]

def seed_privilege_graph():
    """Create and seed the privilege graph collection"""
    print("\n→ Initialising privilege graph in Firestore...")
    
    try:
        # Seed roles
        roles_ref = db.collection("privilege_graph").document("roles")
        roles_data = {}
        for role_name, role_info in ROLES.items():
            roles_data[role_name] = role_info
        roles_ref.set({"roles": roles_data, "created_at": datetime.now().isoformat()})
        print(f"  ✓ {len(ROLES)} roles seeded")
        
        # Seed resources
        resources_ref = db.collection("privilege_graph").document("resources")
        resources_data = {}
        for resource in RESOURCES:
            resources_data[resource["id"]] = resource
        resources_ref.set({"resources": resources_data, "created_at": datetime.now().isoformat()})
        print(f"  ✓ {len(RESOURCES)} resources seeded")
        
    except Exception as e:
        print(f"  ❌ Error seeding privilege graph: {e}")
        raise

def create_sample_users():
    """Create sample users in Firestore"""
    print("\n→ Creating sample users...")
    
    try:
        users_ref = db.collection("users")
        created_count = 0
        
        for user in SAMPLE_USERS:
            users_ref.document(user["user_id"]).set(user)
            print(f"  ✓ Created user: {user['name']} ({user['role']})")
            created_count += 1
        
        print(f"  ✓ {created_count} users created")
        
    except Exception as e:
        print(f"  ❌ Error creating users: {e}")
        raise

def initialize_collections():
    """Initialize all required collections"""
    print("\n→ Initializing Firestore collections...")
    
    collections = [
        "users",
        "login_events",
        "risk_scores",
        "behavioral_dna",
        "anomalies",
        "sessions",
        "privilege_graph",
        "_meta"
    ]
    
    try:
        # Create a document in each collection to ensure it exists
        for collection_name in collections:
            # Check if collection exists by trying to get docs
            docs = db.collection(collection_name).limit(1).stream()
            # If no docs, add a placeholder to create the collection
            try:
                next(docs)
            except StopIteration:
                # Collection is empty, create it with a placeholder
                db.collection(collection_name).document("_placeholder").set({
                    "placeholder": True,
                    "created_at": datetime.now().isoformat()
                })
        
        print(f"  ✓ {len(collections)} collections initialized")
        
    except Exception as e:
        print(f"  ❌ Error initializing collections: {e}")
        raise

def write_metadata():
    """Write schema metadata"""
    print("\n→ Writing collection metadata...")
    
    try:
        meta_ref = db.collection("_meta").document("schema_info")
        meta_ref.set({
            "version": "1.0",
            "initialized_at": datetime.now().isoformat(),
            "collections": [
                "users",
                "login_events",
                "risk_scores",
                "behavioral_dna",
                "anomalies",
                "sessions",
                "privilege_graph"
            ],
            "total_users": len(SAMPLE_USERS),
            "total_roles": len(ROLES),
            "total_resources": len(RESOURCES)
        })
        print("  ✓ Metadata written")
        
    except Exception as e:
        print(f"  ❌ Error writing metadata: {e}")
        raise

def main():
    print("=" * 60)
    print("Firebase Schema Initialization Script")
    print("=" * 60)
    
    try:
        # Initialize collections
        initialize_collections()
        
        # Seed privilege graph
        seed_privilege_graph()
        
        # Create sample users
        create_sample_users()
        
        # Write metadata
        write_metadata()
        
        print("\n" + "=" * 60)
        print("✓ Firebase schema initialised successfully!")
        print("=" * 60)
        print("\nSample users created:")
        for user in SAMPLE_USERS:
            print(f"  • {user['name']} ({user['role']}): {user['email']}")
        
        print(f"\nCollections created: {len(['users', 'login_events', 'risk_scores', 'behavioral_dna', 'anomalies', 'sessions', 'privilege_graph'])}")
        print(f"Roles: {len(ROLES)}")
        print(f"Resources: {len(RESOURCES)}")
        
    except Exception as e:
        print(f"\n❌ Schema initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
