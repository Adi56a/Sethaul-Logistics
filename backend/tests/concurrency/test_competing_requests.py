"""
SetuHaul Logistics — Phase 4 Concurrency & Booking Integrity Test Suite
Simulates concurrent multi-threaded requests targeting the same slot.
Proves that SQLite BEGIN IMMEDIATE + ux_active_appointment_per_slot guarantees
zero double-bookings, atomic rollback, and safe conflict reporting.
"""

import os
import shutil
import sqlite3
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

from app.repositories.db import DatabaseRepository, resolve_db_path
from app.services.booking import BookingService
from app.tools.schemas import ResultCode, ConfirmAppointmentInput, BookingResult

TEST_CONCURRENCY_DB = "concurrency_test_fixture.db"


class TestConcurrencyAndIntegrity(unittest.TestCase):
    def setUp(self):
        # Create a fresh isolated copy of the database fixture for concurrency testing
        if os.path.exists(TEST_CONCURRENCY_DB):
            os.remove(TEST_CONCURRENCY_DB)
        shutil.copyfile(resolve_db_path(), TEST_CONCURRENCY_DB)

    def tearDown(self):
        if os.path.exists(TEST_CONCURRENCY_DB):
            try:
                os.remove(TEST_CONCURRENCY_DB)
            except PermissionError:
                pass

    def test_simultaneous_slot_competition(self):
        """
        Simulates two drivers (SHP1006 and SHP1012) selecting the exact same slot
        (SLOT-JAI-047, 12:00-13:00 D4) at the exact same millisecond across separate threads.
        Asserts:
        1. Exactly ONE thread succeeds with BOOKING_CONFIRMED.
        2. Exactly ONE thread receives SLOT_CONFLICT with refreshed alternatives.
        3. Zero double-booking in appointments table.
        4. ux_active_appointment_per_slot index invariant holds.
        """
        target_slot = "SLOT-JAI-047"
        shipment_a = "SHP1006"
        shipment_b = "SHP1012"

        # Barrier to release both threads at the exact same instant
        barrier = threading.Barrier(2)
        results: List[BookingResult] = []
        lock = threading.Lock()

        def attempt_booking(shipment_id: str, idempotency_key: str):
            # Each thread uses its own DatabaseRepository instance (separate connection)
            repo = DatabaseRepository(TEST_CONCURRENCY_DB, timeout=10.0)
            service = BookingService(repo)
            
            payload = ConfirmAppointmentInput(
                shipment_id=shipment_id,
                slot_id=target_slot,
                idempotency_key=idempotency_key
            )
            # Synchronize start to create maximum concurrency contention
            barrier.wait()
            res = service.confirm_appointment(payload)
            with lock:
                results.append(res)

        t1 = threading.Thread(target=attempt_booking, args=(shipment_a, "race-key-A"))
        t2 = threading.Thread(target=attempt_booking, args=(shipment_b, "race-key-B"))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(results), 2, "Expected exactly 2 results from concurrent threads.")

        # Inspect results
        statuses = [r.result_code for r in results]
        print(f"\n[CONCURRENCY RACE RESULT] Thread outcomes: {[s.value for s in statuses]}")

        # Assert exactly one winner and one conflict
        confirmed_count = statuses.count(ResultCode.BOOKING_CONFIRMED)
        conflict_count = statuses.count(ResultCode.SLOT_CONFLICT)

        self.assertEqual(confirmed_count, 1, f"Expected exactly 1 BOOKING_CONFIRMED, got {confirmed_count}")
        self.assertEqual(conflict_count, 1, f"Expected exactly 1 SLOT_CONFLICT, got {conflict_count}")

        # Verify loser received alternative options
        conflict_res = [r for r in results if r.result_code == ResultCode.SLOT_CONFLICT][0]
        self.assertGreater(len(conflict_res.alternative_slots), 0, "Losing request must receive fresh feasible alternatives.")
        print(f"[CONCURRENCY RACE] Loser was offered {len(conflict_res.alternative_slots)} alternative slots (e.g. {conflict_res.alternative_slots[0].slot_id}).")

        # Database State Verification: Assert only 1 active booking on target slot
        repo_verify = DatabaseRepository(TEST_CONCURRENCY_DB)
        active_bookings = repo_verify.fetch_all("""
            SELECT appointment_id, shipment_id, slot_id, appointment_status, is_current
            FROM appointments
            WHERE slot_id = ?
              AND appointment_status IN ('PENDING_CONFIRMATION', 'CONFIRMED', 'IN_PROGRESS');
        """, (target_slot,))

        self.assertEqual(len(active_bookings), 1, "Database MUST have exactly 1 active appointment for the slot.")
        print(f"[DATABASE INTEGRITY] Winner in DB: Appointment {active_bookings[0]['appointment_id']} for {active_bookings[0]['shipment_id']}.")

    def test_idempotent_retry_handling(self):
        """
        Tests that retrying the exact same booking command multiple times
        (e.g. on client network timeout) safely returns the existing confirmation
        without creating duplicate rows or crashing with constraint errors.
        """
        repo = DatabaseRepository(TEST_CONCURRENCY_DB)
        service = BookingService(repo)
        payload = ConfirmAppointmentInput(
            shipment_id="SHP1006",
            slot_id="SLOT-JAI-047",
            idempotency_key="idempotent-key-999"
        )

        # 1. First execution
        res1 = service.confirm_appointment(payload)
        self.assertEqual(res1.result_code, ResultCode.BOOKING_CONFIRMED)
        first_apt_id = res1.appointment_id

        # 2. Replayed retry
        res2 = service.confirm_appointment(payload)
        self.assertIn(res2.result_code, [ResultCode.BOOKING_CONFIRMED, ResultCode.IDEMPOTENT_REPLAY])
        self.assertEqual(res2.appointment_id, first_apt_id)

        # 3. Verify exactly 1 record exists in appointments
        count_row = repo.fetch_one("""
            SELECT COUNT(*) AS c 
            FROM appointments 
            WHERE shipment_id = 'SHP1006' AND slot_id = 'SLOT-JAI-047';
        """)
        self.assertEqual(count_row["c"], 1)

    def test_single_active_appointment_per_shipment(self):
        """
        Verifies partial unique index ux_current_active_appointment_per_shipment.
        When a shipment is rescheduled to a new slot, its previous active appointment
        must be updated to is_current = 0 so the shipment holds at most 1 current active slot.
        """
        repo = DatabaseRepository(TEST_CONCURRENCY_DB)
        service = BookingService(repo)

        # Book first slot
        payload1 = ConfirmAppointmentInput(
            shipment_id="SHP1006",
            slot_id="SLOT-JAI-047",
            idempotency_key="seq-key-1"
        )
        service.confirm_appointment(payload1)

        # Reschedule same shipment to a later open slot (SLOT-JAI-048 at 13:00)
        payload2 = ConfirmAppointmentInput(
            shipment_id="SHP1006",
            slot_id="SLOT-JAI-048",
            idempotency_key="seq-key-2"
        )
        res2 = service.confirm_appointment(payload2)
        self.assertEqual(res2.result_code, ResultCode.BOOKING_CONFIRMED)

        # Verify only 1 active appointment has is_current = 1
        active_apts = repo.fetch_all("""
            SELECT appointment_id, slot_id, is_current, appointment_status
            FROM appointments
            WHERE shipment_id = 'SHP1006'
              AND is_current = 1
              AND appointment_status IN ('PENDING_CONFIRMATION', 'CONFIRMED', 'IN_PROGRESS');
        """)
        self.assertEqual(len(active_apts), 1)
        self.assertEqual(active_apts[0]["slot_id"], "SLOT-JAI-048")


if __name__ == "__main__":
    unittest.main()
