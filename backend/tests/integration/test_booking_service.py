"""
SetuHaul Logistics — Booking Service Integration Tests
Tests atomic booking transitions, revalidation, cancellations, and escalations
against an isolated copy of the database fixture.
"""

import os
import shutil
import unittest
from app.repositories.db import DatabaseRepository, resolve_db_path
from app.services.booking import BookingService
from app.tools.schemas import ResultCode, ConfirmAppointmentInput

TEST_DB_PATH = "test_setuhaul_fixture.db"


class TestBookingService(unittest.TestCase):
    def setUp(self):
        # Create an isolated copy of the database fixture for every test
        shutil.copyfile(resolve_db_path(), TEST_DB_PATH)
        self.repo = DatabaseRepository(TEST_DB_PATH)
        self.service = BookingService(self.repo)

    def tearDown(self):
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def test_record_eta_update(self):
        """Records a new ETA update and verifies shipments.latest_eta_ts is updated."""
        res = self.service.record_eta_update(
            shipment_id="SHP1006",
            declared_eta_ts="2026-08-04T11:45:00+05:30",
            source_type="DRIVER_DECLARED",
            confidence_code="HIGH",
            delay_reason_code="TRAFFIC",
            note="Tyre issue cleared, moving fast."
        )
        self.assertEqual(res["result_code"], ResultCode.AVAILABLE)
        
        # Verify in DB
        shp = self.repo.fetch_one("SELECT latest_eta_ts FROM shipments WHERE shipment_id = 'SHP1006';")
        self.assertEqual(shp["latest_eta_ts"], "2026-08-04T11:45:00+05:30")

    def test_confirm_appointment_success(self):
        """Confirms an open slot (SLOT-JAI-047, 12:00 D4) for SHP1006; verifies prior appointment deactivation."""
        # Previous active appointment was APT1006 on SLOT-JAI-045
        prev = self.repo.fetch_one("SELECT appointment_id, is_current FROM appointments WHERE shipment_id = 'SHP1006' AND is_current = 1;")
        self.assertEqual(prev["appointment_id"], "APT1006")

        payload = ConfirmAppointmentInput(
            shipment_id="SHP1006",
            slot_id="SLOT-JAI-047",
            idempotency_key="key-test-001"
        )
        res = self.service.confirm_appointment(payload)
        self.assertEqual(res.result_code, ResultCode.BOOKING_CONFIRMED)
        self.assertEqual(res.status, "CONFIRMED")
        self.assertEqual(res.slot_id, "SLOT-JAI-047")

        # Verify old appointment is deactivated
        old_apt = self.repo.fetch_one("SELECT is_current, cancellation_reason FROM appointments WHERE appointment_id = 'APT1006';")
        self.assertEqual(old_apt["is_current"], 0)
        self.assertIn("Rescheduled to SLOT-JAI-047", old_apt["cancellation_reason"])

        # Verify new appointment is current
        new_apt = self.repo.fetch_one("SELECT appointment_id, slot_id, is_current, appointment_status FROM appointments WHERE shipment_id = 'SHP1006' AND is_current = 1;")
        self.assertEqual(new_apt["slot_id"], "SLOT-JAI-047")
        self.assertEqual(new_apt["appointment_status"], "CONFIRMED")

    def test_conflict_on_already_occupied_slot(self):
        """Attempting to book a slot already occupied (SLOT-JAI-046 occupied by SHP1009) must return SLOT_CONFLICT."""
        payload = ConfirmAppointmentInput(
            shipment_id="SHP1006",
            slot_id="SLOT-JAI-046",  # Occupied by SHP1009
            idempotency_key="key-test-002"
        )
        res = self.service.confirm_appointment(payload)
        self.assertEqual(res.result_code, ResultCode.SLOT_CONFLICT)
        self.assertEqual(res.status, "CONFLICT")
        self.assertGreater(len(res.alternative_slots), 0)

    def test_release_appointment(self):
        """Releasing an appointment marks it CANCELLED with is_current = 0."""
        res = self.service.release_appointment("APT1006", reason="Driver delayed past window")
        self.assertEqual(res["status"], "CANCELLED")
        
        apt = self.repo.fetch_one("SELECT appointment_status, is_current FROM appointments WHERE appointment_id = 'APT1006';")
        self.assertEqual(apt["appointment_status"], "CANCELLED")
        self.assertEqual(apt["is_current"], 0)

    def test_human_escalation_creation(self):
        """Creates an escalation ticket in driver_exceptions and marks thread ESCALATED."""
        res = self.service.create_human_escalation(
            thread_id="THR005",
            driver_id="DRV015",
            shipment_id="SHP1015",
            description="Reefer dock D5 under maintenance until 22:00. Zero capacity."
        )
        self.assertEqual(res["status"], "ESCALATED")
        
        thread = self.repo.fetch_one("SELECT thread_status FROM chat_threads WHERE thread_id = 'THR005';")
        self.assertEqual(thread["thread_status"], "ESCALATED")


if __name__ == "__main__":
    unittest.main()
