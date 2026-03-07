import requests
import unittest
import uuid
from datetime import date

BASE_URL = "http://localhost:8000/api"

class TestInterpolationAPI(unittest.TestCase):
    def test_workflow(self):
        # 1. Create Group
        group_name = f"Test Group {uuid.uuid4()}"
        print(f"Creating group: {group_name}")
        r = requests.post(f"{BASE_URL}/groups", json={"name": group_name, "description": "Test Desc", "id": ""})
        self.assertEqual(r.status_code, 200)
        group = r.json()
        group_id = group["id"]
        print(f"Group created: {group_id}")

        # 2. Add Payment
        print("Adding payment...")
        payment_payload = {
            "id": "",
            "group_id": group_id,
            "amount": 123.45,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "note": "Test Note"
        }
        r = requests.post(f"{BASE_URL}/groups/{group_id}/payments", json=payment_payload)
        self.assertEqual(r.status_code, 200)
        payment = r.json()
        payment_id = payment["id"]
        print(f"Payment created: {payment_id}")

        # 3. Verify Payment
        r = requests.get(f"{BASE_URL}/groups/{group_id}/payments")
        self.assertEqual(r.status_code, 200)
        payments = r.json()
        self.assertTrue(any(p["id"] == payment_id for p in payments))
        print("Payment verified")

        # 4. Clean up (Delete Group)
        print("Deleting group...")
        r = requests.delete(f"{BASE_URL}/groups/{group_id}")
        self.assertEqual(r.status_code, 200)
        
        # Verify deletion
        r = requests.get(f"{BASE_URL}/groups")
        groups = r.json()
        self.assertFalse(any(g["id"] == group_id for g in groups))
        print("Cleanup verified")

if __name__ == "__main__":
    unittest.main()
