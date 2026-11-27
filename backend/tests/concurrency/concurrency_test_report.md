# SetuHaul Logistics — Concurrency & Booking Integrity Report

**Test Milestone:** Phase 4 Verification  
**Test Script:** `tests/concurrency/test_competing_requests.py`  
**Execution Timestamp:** 19 November 2026, Asia/Kolkata (`+05:30`)  
**Target Fixture:** SQLite Snapshot (`setuhaul_freight_operations.db`)

---

## 1. Executive Summary

A critical requirement of the SetuHaul Logistics platform is guaranteeing that **two competing drivers requesting the same dock slot at nearly the same time can never both be confirmed for that slot** (zero double-bookings).

The platform enforces this guarantee through:
1. **SQLite Storage Engine Defense:** Partial unique index `ux_active_appointment_per_slot` on `appointments(slot_id)` where `appointment_status IN ('PENDING_CONFIRMATION','CONFIRMED','IN_PROGRESS')`.
2. **Transaction Isolation:** All slot commitment writes execute inside Python `sqlite3` using `BEGIN IMMEDIATE` transactions with a 10-second busy timeout.
3. **Structured Conflict Recovery:** When a competing thread encounters an `IntegrityError`, it immediately rolls back and returns a structured `SLOT_CONFLICT` response accompanied by fresh feasible alternative slots.

---

## 2. Test Execution & Evidence

### Test Scenario 1: Competing Requests for the Same Capacity
- **Contested Slot:** `SLOT-JAI-047` (Jaipur DC, Dock D4, 12:00:00 to 13:00:00+05:30)
- **Competing Shipments:**
  - Thread 1: `SHP1006` (Manoj Sharma, High Priority)
  - Thread 2: `SHP1012` (Arjun Das, Normal Priority)
- **Synchronization Mechanism:** `threading.Barrier(2)` releases both threads at the exact same microsecond.

#### Before-Test State (Query on Database):
```sql
SELECT slot_id, dock_id, slot_status FROM appointment_slots WHERE slot_id = 'SLOT-JAI-047';
-- Result: 'SLOT-JAI-047' | 'DOCK-JAI-D4' | 'OPEN'

SELECT COUNT(*) FROM appointments 
WHERE slot_id = 'SLOT-JAI-047' 
  AND appointment_status IN ('PENDING_CONFIRMATION','CONFIRMED','IN_PROGRESS');
-- Result: 0 active bookings
```

#### Race Execution Log:
```text
[CONCURRENCY RACE RESULT] Thread outcomes: ['BOOKING_CONFIRMED', 'SLOT_CONFLICT']
[CONCURRENCY RACE] Loser was offered 36 alternative slots (e.g. SLOT-JAI-019).
[DATABASE INTEGRITY] Winner in DB: Appointment APT-A07C1FA7 for SHP1006.
```

#### After-Test State (Query on Database):
```sql
SELECT appointment_id, shipment_id, slot_id, appointment_status, is_current 
FROM appointments 
WHERE slot_id = 'SLOT-JAI-047';
-- Result: Exactly 1 row ('APT-A07C1FA7', 'SHP1006', 'SLOT-JAI-047', 'CONFIRMED', 1)
```

---

## 3. Test Scenario 2: Idempotent Retries
- **Purpose:** Verifies that network retries or replayed webhook messages containing the same booking command do not duplicate appointments or raise crash errors.
- **Result:**
  - Initial Call: Returned `BOOKING_CONFIRMED` with new appointment ID.
  - Replayed Call: Recognized existing commitment; returned `IDEMPOTENT_REPLAY` with the exact same appointment ID.
  - Row Count in `appointments`: Exactly 1 row.

---

## 4. Test Scenario 3: Single Active Appointment per Shipment
- **Purpose:** Verifies partial unique index `ux_current_active_appointment_per_shipment`.
- **Action:** Shipment `SHP1006` booked `SLOT-JAI-047` and was subsequently rescheduled to `SLOT-JAI-048`.
- **Result:**
  - Previous appointment was updated to `is_current = 0, cancellation_reason = 'Rescheduled to SLOT-JAI-048'`.
  - New appointment inserted with `is_current = 1`.
  - Exactly 1 current active appointment found for `SHP1006`.

---

## 5. Phase 4 Exit Criteria Checklist

| Exit Criterion | Status | Evidence |
|---|---|---|
| Repeatable concurrency test proves at most one active booking per slot | **PASSED** | `tests/concurrency/test_competing_requests.py` (Asserted 1 confirmed, 1 conflict) |
| At most one current active appointment per shipment | **PASSED** | Enforced by `ux_current_active_appointment_per_shipment` in Test 3 |
| Losing request receives a structured conflict and refreshed options | **PASSED** | Loser received `ResultCode.SLOT_CONFLICT` and 36 feasible alternative slots |
| No false confirmation is sent | **PASSED** | Only the transaction with confirmed DB commit receives `BOOKING_CONFIRMED` |
| SQLite database passes integrity checks | **PASSED** | `PRAGMA integrity_check` verified 'ok' |
