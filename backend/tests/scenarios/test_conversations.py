"""
SetuHaul Logistics — Phase 5 Conversational Scenario Suite
Evaluates full multi-turn conversations: delay reports, clarification turns,
competing option selection, and human escalations.
"""

import os
import shutil
import unittest
from app.repositories.db import DatabaseRepository, resolve_db_path
from app.agent.tools import set_custom_repo
from app.agent.agent import SetuHaulAgent

TEST_CONVO_DB = "convo_test_fixture.db"


class TestConversationalScenarios(unittest.TestCase):
    def setUp(self):
        # Create an isolated database fixture for conversation tests
        import gc; gc.collect()
        if os.path.exists(TEST_CONVO_DB):
            try:
                os.remove(TEST_CONVO_DB)
            except Exception:
                pass
        shutil.copyfile(resolve_db_path(), TEST_CONVO_DB)
        self.repo = DatabaseRepository(TEST_CONVO_DB)
        set_custom_repo(self.repo)
        self.agent = SetuHaulAgent()

    def tearDown(self):
        import gc; gc.collect()
        if os.path.exists(TEST_CONVO_DB):
            try:
                os.remove(TEST_CONVO_DB)
            except Exception:
                pass

    def test_scenario_journey_a_delay_and_reschedule(self):
        """
        Journey A: Driver Manoj Sharma (DRV006, SHP1006) reports delay.
        Turn 1: Driver reports traffic and ETA 11:20. Agent presents feasible standard slots (D2, D4 at 12:00 PM).
        Turn 2: Driver chooses Dock D4. Agent confirms booking and issues appointment ref.
        """
        thread_id = "test_journey_a_001"
        driver_id = "DRV006"

        # Turn 1: Report delay with order reference
        turn1 = self.agent.chat(
            user_message="Traffic after Shahpura for ORD-260804-006. Reaching around 11:20. Any slot after 12?",
            thread_id=thread_id,
            driver_id=driver_id
        )
        self.assertEqual(turn1["status"], "OPTIONS_PRESENTED")
        self.assertIn("12:00 PM", turn1["response"])
        self.assertIn("D4", turn1["response"])

        # Turn 2: Driver chooses D4
        turn2 = self.agent.chat(
            user_message="Please book Dock D4 at 12:00 PM for me.",
            thread_id=thread_id,
            driver_id=driver_id
        )
        self.assertEqual(turn2["status"], "CONFIRMED")
        self.assertIn("Confirmed", turn2["response"])
        self.assertIn("D4", turn2["response"])

        # Verify DB state
        apt = self.repo.fetch_one("""
            SELECT appointment_id, slot_id, appointment_status, is_current
            FROM appointments
            WHERE shipment_id = 'SHP1006' AND is_current = 1;
        """)
        self.assertEqual(apt["slot_id"], "SLOT-JAI-047")
        self.assertEqual(apt["appointment_status"], "CONFIRMED")

    def test_scenario_ambiguous_shipment_clarification(self):
        """
        Driver Sandeep Meena (DRV004) has 2 active shipments (SHP1004 & SHP1020).
        Turn 1: Driver sends vague delay.
        Agent asks clarification turn on order references without booking or guessing.
        """
        turn1 = self.agent.chat(
            user_message="I will be late by 45 minutes.",
            thread_id="test_ambig_001",
            driver_id="DRV004"
        )
        self.assertEqual(turn1["status"], "AWAITING_CLARIFICATION")
        self.assertIn("ORD-260804-004", turn1["response"])
        self.assertIn("ORD-260804-020", turn1["response"])

    def test_scenario_reefer_dock_breakdown_escalation(self):
        """
        Shipment SHP1015 (Reefer load) has ETA 18:30, but D5 is under maintenance.
        Agent finds 0 feasible slots and creates human escalation record.
        """
        res = self.agent.chat(
            user_message="Evening traffic entering Jaipur. ETA 18:30. Need reefer dock tonight.",
            thread_id="test_reefer_esc_001",
            driver_id="DRV015"
        )
        self.assertEqual(res["status"], "ESCALATED")
        self.assertIn("escalated", res["response"].lower())

        # Verify escalation in database
        exc = self.repo.fetch_one("""
            SELECT exception_id, exception_status, thread_id 
            FROM driver_exceptions 
            WHERE thread_id = 'test_reefer_esc_001';
        """)
        self.assertIsNotNone(exc)
        self.assertEqual(exc["exception_status"], "ESCALATED")


if __name__ == "__main__":
    unittest.main()
