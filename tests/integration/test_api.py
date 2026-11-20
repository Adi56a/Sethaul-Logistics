"""
SetuHaul Logistics — FastAPI Service Boundary Integration Tests
Tests HTTP endpoints: Health check, Chat, Feasibility, Bookings, and Escalation Queue.
"""

import os
import shutil
import unittest
from fastapi.testclient import TestClient

from app.api.main import app
from app.repositories.db import DatabaseRepository
from app.services.feasibility import FeasibilityService
from app.services.booking import BookingService
from app.agent.agent import SetuHaulAgent

TEST_API_DB = "api_test_fixture.db"


class TestAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.path.exists(TEST_API_DB):
            os.remove(TEST_API_DB)
        shutil.copyfile("setuhaul_freight_operations.db", TEST_API_DB)
        
        # Inject test database
        from app.api import main
        main.repo = DatabaseRepository(TEST_API_DB)
        main.feasibility = FeasibilityService(main.repo)
        main.booking = BookingService(main.repo, main.feasibility)
        main.agent = SetuHaulAgent()

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_API_DB):
            try:
                os.remove(TEST_API_DB)
            except PermissionError:
                pass

    def test_health_endpoint(self):
        """GET /health returns 200 with status PASS."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "PASS")

    def test_get_shipment_context(self):
        """GET /api/shipments/SHP1006 returns full operational context."""
        response = self.client.get("/api/shipments/SHP1006")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["shipment_id"], "SHP1006")
        self.assertEqual(data["destination_facility_id"], "FAC-JAI-01")

    def test_get_feasible_slots(self):
        """GET /api/slots/feasible returns feasible slot list."""
        response = self.client.get("/api/slots/feasible?shipment_id=SHP1006&min_time=2026-08-04T11:20:00%2B05:30")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["result_code"], "AVAILABLE")
        self.assertGreater(len(data["feasible_slots"]), 0)

    def test_chat_endpoint_multi_shipment_clarification(self):
        """POST /api/chat triggers clarification on driver with dual shipments."""
        payload = {
            "message": "I am delayed by 45 minutes on highway.",
            "thread_id": "api_thr_001",
            "driver_id": "DRV004"
        }
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "AWAITING_CLARIFICATION")
        self.assertIn("ORD-260804-004", data["response"])

    def test_get_operations_escalations(self):
        """GET /api/operations/escalations returns active exception tickets."""
        response = self.client.get("/api/operations/escalations")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data["count"], 1)

    def test_resolve_escalation(self):
        """POST /api/operations/resolve updates exception status to RESOLVED."""
        payload = {
            "exception_id": "EXC005",
            "resolution_note": "Reassigned to morning shift slot upon reopening.",
            "action": "MANUAL_RESCHEDULE"
        }
        response = self.client.post("/api/operations/resolve", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
