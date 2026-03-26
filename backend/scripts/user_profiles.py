import hashlib

USERS = [
    {
        "id":          "alice_eng",
        "role":        "engineer",
        "sensitivity_ceiling": 5,      # max resource sensitivity for role
        "country":     "IN",
        "city":        "Mumbai",
        "lat":         19.0760,         # for haversine travel detection
        "lon":         72.8777,
        "hours":       (9, 18),         # typical login window
        "hour_std":    1.5,             # how much variation is normal
        "weekend_bias": 0.1,            # probability of weekend login
        "resources":   ["dev_dashboard", "staging_api", "reports"],
        "device_count": 2,             # primary + sometimes secondary
        "login_freq_per_week": 5,
    },
    {
        "id":          "bob_admin",
        "role":        "superadmin",
        "sensitivity_ceiling": 10,
        "country":     "IN",
        "city":        "Delhi",
        "lat":         28.6139,
        "lon":         77.2090,
        "hours":       (8, 20),
        "hour_std":    2.5,             # admins have more varied hours
        "weekend_bias": 0.3,
        "resources":   ["iam_console","user_mgmt","billing_panel","reports"],
        "device_count": 1,             # admins usually stick to one machine
        "login_freq_per_week": 7,
    },
    {
        "id":          "carol_fin",
        "role":        "finance",
        "sensitivity_ceiling": 9,
        "country":     "IN",
        "city":        "Bangalore",
        "lat":         12.9716,
        "lon":         77.5946,
        "hours":       (10, 19),
        "hour_std":    1.0,             # finance staff are very consistent
        "weekend_bias": 0.05,
        "resources":   ["billing_panel", "reports", "payroll_system"],
        "device_count": 1,
        "login_freq_per_week": 5,
    },
    {
        "id":          "dave_dev",
        "role":        "developer",
        "sensitivity_ceiling": 5,
        "country":     "IN",
        "city":        "Chennai",
        "lat":         13.0827,
        "lon":         80.2707,
        "hours":       (11, 23),        # developers work late
        "hour_std":    2.0,
        "weekend_bias": 0.25,
        "resources":   ["dev_dashboard", "staging_api", "git_server"],
        "device_count": 3,             # devs use multiple machines
        "login_freq_per_week": 7,
    },
    {
        "id":          "eve_hr",
        "role":        "hr_manager",
        "sensitivity_ceiling": 6,
        "country":     "IN",
        "city":        "Hyderabad",
        "lat":         17.3850,
        "lon":         78.4867,
        "hours":       (9, 17),         # strict 9-5 pattern
        "hour_std":    0.8,
        "weekend_bias": 0.02,           # almost never works weekends
        "resources":   ["hr_portal", "reports", "user_mgmt"],
        "device_count": 1,
        "login_freq_per_week": 5,
    },
]

# Resource sensitivity — the core of the privilege graph
RESOURCES = {
    "dev_dashboard":    1,   # low — internal tool, read-only
    "git_server":       2,   # low — source code access
    "reports":          3,   # low — business intelligence, read-only
    "hr_portal":        4,   # medium — employee personal data
    "staging_api":      5,   # medium — can affect test environment
    "payroll_system":   6,   # medium-high — financial data
    "user_mgmt":        6,   # medium-high — can modify user accounts
    "billing_panel":    9,   # high — financial transactions
    "iam_console":      10,  # critical — controls all access
}

def device_id(user_id, variant=0):
    """variant=0 is always primary device. variant=1,2,3 are secondary."""
    seed = f"{user_id}_device_{variant}"
    return hashlib.md5(seed.encode()).hexdigest()[:14]
