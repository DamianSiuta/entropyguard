"""Quick test script to generate critical alerts from payment-gateway."""
import requests
import time
import json

API_BASE_URL = "http://localhost:8000"
API_TOKEN_URL = f"{API_BASE_URL}/auth/token"
API_AUDIT_URL = f"{API_BASE_URL}/api/v1/telemetry/audit"

# Login
print("[LOGIN] Logging in...")
form_data = {'username': 'admin', 'password': 'admin'}
response = requests.post(API_TOKEN_URL, data=form_data, headers={'Content-Type': 'application/x-www-form-urlencoded'})

if response.status_code != 200:
    print(f"[ERROR] Login failed: {response.status_code}")
    exit(1)

token = response.json()['access_token']
print("[OK] Logged in successfully!")

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {token}'
}

# Send 5 critical logs from payment-gateway
print("\n[SENDING] Sending 5 critical logs from payment-gateway...")
for i in range(5):
    entry = {
        "source": "payment-gateway",
        "message": f"Critical payment error #{i+1}",
        "event_type": "critical",
        "user_id": f"user-{i+1:04d}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "metadata": {
            "session_id": f"session-{1000+i}",
            "request_id": f"req-{10000+i}",
            "duration_ms": 500,
            "status_code": 500,
        }
    }
    
    response = requests.post(
        API_AUDIT_URL,
        json={"data": entry},
        headers=headers
    )
    
    if response.status_code in [200, 201]:
        result = response.json()
        print(f"[OK] [{i+1}/5] Sent critical log (ID: {result.get('id')})")
    else:
        print(f"[ERROR] [{i+1}/5] Failed: {response.status_code} - {response.text}")
    
    time.sleep(0.5)  # Small delay between requests

print("\n[OK] Test completed! Check the Alerts page in the dashboard.")
print("   Expected: Alert should be triggered if rule threshold is <= 5")

