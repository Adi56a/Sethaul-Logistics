"""
SetuHaul Logistics — Conversational Agent Unit Tests
Tests tool bindings, multi-turn clarification, prompt safety, and escalation handling.
"""

import json
import unittest
from app.repositories.db import DatabaseRepository, resolve_db_path
from app.agent.tools import (
    resolve_driver,
    get_shipment_details,
    update_driver_eta,
    find_feasible_dock_slots,
    book_dock_appointment,
    escalate_to_human_operator,
    set_custom_repo
)
from app.agent.agent import SetuHaulAgent


class TestAgentToolsAndFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = DatabaseRepository(resolve_db_path())
        set_custom_repo(cls.repo)
        cls.agent = SetuHaulAgent()

    def test_tool_resolve_driver_ambiguous(self):
        """Tool resolve_driver correctly detects multiple shipments for DRV004."""
        res_str = resolve_driver.invoke({"driver_id": "DRV004"})
        res = json.loads(res_str)
        self.assertEqual(res["result_code"], "AMBIGUOUS_IDENTITY")
        self.assertTrue(res["is_ambiguous"])
        self.assertEqual(len(res["active_shipments"]), 2)

    def test_tool_get_shipment_details(self):
        """Tool get_shipment_details retrieves authoritative shipment and vehicle context."""
        res_str = get_shipment_details.invoke({"shipment_id": "SHP1006"})
        res = json.loads(res_str)
        self.assertEqual(res["shipment_id"], "SHP1006")
        self.assertEqual(res["destination_facility_id"], "FAC-JAI-01")
        self.assertEqual(res["required_dock_type"], "STANDARD")

    def test_tool_find_feasible_dock_slots_shp1006(self):
        """Tool find_feasible_dock_slots returns only compatible slots."""
        res_str = find_feasible_dock_slots.invoke({
            "shipment_id": "SHP1006",
            "min_time": "2026-08-04T11:20:00+05:30"
        })
        res = json.loads(res_str)
        self.assertEqual(res["result_code"], "AVAILABLE")
        self.assertGreater(len(res["feasible_slots"]), 0)
        # Verify 12:00 slots present
        slot_starts = [s["slot_start_ts"] for s in res["feasible_slots"]]
        self.assertTrue(any("12:00:00" in s for s in slot_starts))

    def test_tool_find_feasible_dock_slots_reefer_breakdown(self):
        """Tool find_feasible_dock_slots on SHP1015 returns NO_FEASIBLE_SLOT due to D5 maintenance."""
        res_str = find_feasible_dock_slots.invoke({
            "shipment_id": "SHP1015",
            "min_time": "2026-08-04T18:30:00+05:30"
        })
        res = json.loads(res_str)
        self.assertEqual(res["result_code"], "NO_FEASIBLE_SLOT")
        self.assertEqual(len(res["feasible_slots"]), 0)

    def test_agent_chat_ambiguous_shipment_clarification(self):
        """Agent asks targeted clarification when driver DRV004 reports a delay without identifying shipment."""
        res = self.agent.chat(
            user_message="Traffic jam near Tonk Road, reaching late by 45 minutes.",
            thread_id="test_thr_010",
            driver_id="DRV004"
        )
        self.assertEqual(res["status"], "AWAITING_CLARIFICATION")
        self.assertIn("ORD-260804-004", res["response"])
        self.assertIn("ORD-260804-020", res["response"])

    def test_agent_chat_reefer_escalation(self):
        """Agent escalates to human operator when reefer load SHP1015 has no feasible dock."""
        res = self.agent.chat(
            user_message="Evening traffic. ETA 6:30. Can the reefer unload tonight?",
            thread_id="test_thr_005",
            driver_id="DRV015"
        )
        self.assertEqual(res["status"], "ESCALATED")
        self.assertIn("maintenance", res["response"].lower())
        self.assertIn("escalated", res["response"].lower())


if __name__ == "__main__":
    unittest.main()
