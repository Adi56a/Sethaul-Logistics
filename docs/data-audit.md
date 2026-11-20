# SetuHaul Freight Operations — Comprehensive Data Audit & Verification

**Audit Date:** 4 August 2026 (Operational Snapshot: Asia/Kolkata +05:30)  
**Database File:** `setuhaul_freight_operations.db`  
**Seed SQL Script:** `setuhaul_schema_and_seed.sql`  
**Audit Scope:** 18 Tables, 4 Views, 2 Partial Unique Indexes, 5 B-Tree Indexes, Foreign Key Constraints, and 22 Seeded Scenarios.

---

## 1. Schema & Table Inventory Verification

Every table count below was directly verified against `setuhaul_freight_operations.db`.

| # | Table Name | Purpose | Verified Row Count | Status & Constraints |
|---|---|---|---|---|
| 1 | `carriers` | Freight transport operators providing fleet | 4 | Validated; `active_flag IN (0,1)` |
| 2 | `drivers` | Commercial drivers assigned to carriers | 15 | Validated; phone & licence unique |
| 3 | `vehicle_types` | Standard vehicle classes & dock profiles | 5 | Validated; 20FT, 32FT_SXL, 32FT_MXL, REEFER_32, HEAVY_40 |
| 4 | `vehicles` | Physical motorized trucks & trailers | 15 | Validated; registration unique |
| 5 | `facilities` | Distribution centres & cross-docks | 2 | Validated; FAC-JAI-01 (Jaipur DC), FAC-GGN-01 (Gurugram) |
| 6 | `docks` | Physical bays at facilities | 9 | Validated; JAI: D1–D4 (Std), D5 (Reefer), D6 (Heavy); GGN: D1–D2 (Std), D3 (Reefer) |
| 7 | `facility_contacts` | Warehouse managers & gate supervisors | 5 | Contact gap found: CON005 email is NULL |
| 8 | `facility_rules` | Timing, grace periods, & physical constraints | 6 | 5 rules for Jaipur DC, 1 rule for Gurugram |
| 9 | `shipments` | Freight orders between origin and destination | 21 | Orders ORD-260804-001 through 021 |
| 10 | `eta_updates` | Historical & active declared arrival estimates | 12 | Original plan, driver declared, & low confidence |
| 11 | `appointment_slots` | Dock resource time slots (1 hr / 1.5 hr) | 106 | 79 at Jaipur, 27 at Gurugram |
| 12 | `appointments` | Bookings connecting shipments to slots | 20 | Confirmed, in-progress, pending, cancelled, no-show |
| 13 | `dock_status_events` | Breakdowns, maintenance, capacity events | 3 | DEVT001 (breakdown), DEVT002 (maintenance), DEVT003 (overrun) |
| 14 | `facility_checkins` | Physical gate, yard, and dock timestamps | 5 | Real-time physical truck states |
| 15 | `chat_threads` | Multi-turn driver communication threads | 12 | Threads THR001 through THR012 |
| 16 | `chat_messages` | Inbound/outbound conversational messages | 20 | Messages MSG001 through MSG020 |
| 17 | `driver_exceptions` | Structured delay and operational exceptions | 10 | Exceptions EXC001 through EXC010 |
| 18 | `operational_messages` | Warehouse notifications & confirmations | 5 | Email & SMS transmissions |

---

## 2. Integrity & Constraint Verification Queries

### 2.1 Foreign Key and Database Integrity Check
```sql
PRAGMA foreign_key_check;
-- Result: 0 violations (database maintains perfect referential integrity)

PRAGMA integrity_check;
-- Result: "ok"
```

### 2.2 Partial Unique Indexes (Booking Concurrency & History Guards)
The database enforces slot booking integrity through two partial unique indexes:
```sql
-- Guard 1: Prevents double-booking any slot across active statuses
CREATE UNIQUE INDEX ux_active_appointment_per_slot
ON appointments(slot_id)
WHERE appointment_status IN ('PENDING_CONFIRMATION','CONFIRMED','IN_PROGRESS');

-- Guard 2: Prevents a shipment from holding multiple active appointments concurrently
CREATE UNIQUE INDEX ux_current_active_appointment_per_shipment
ON appointments(shipment_id)
WHERE is_current = 1
  AND appointment_status IN ('PENDING_CONFIRMATION','CONFIRMED','IN_PROGRESS');
```
*Verification Query:*
```sql
SELECT slot_id, COUNT(*) 
FROM appointments 
WHERE appointment_status IN ('PENDING_CONFIRMATION','CONFIRMED','IN_PROGRESS') 
GROUP BY slot_id HAVING COUNT(*) > 1;
-- Output: 0 rows (No double bookings exist in snapshot)

SELECT shipment_id, COUNT(*) 
FROM appointments 
WHERE is_current = 1 AND appointment_status IN ('PENDING_CONFIRMATION','CONFIRMED','IN_PROGRESS') 
GROUP BY shipment_id HAVING COUNT(*) > 1;
-- Output: 0 rows (No shipment holds more than one current active slot)
```

---

## 3. Audited Edge Cases & Data Anomalies (With SQL Proof)

### 3.1 Contact Information Gap: CON005 Missing Email
**Finding:** Contact `CON005` (Night Shift Coordinator at `FAC-GGN-01`) has a phone number but a `NULL` email address. Any automated warehouse notification tool routing confirmation emails to this contact will fail unless a phone/SMS fallback is configured.
```sql
SELECT contact_id, facility_id, contact_role, contact_name, email, phone 
FROM facility_contacts 
WHERE email IS NULL;
```
*Actual Database Output:*
`CON005 | FAC-GGN-01 | NIGHT_SHIFT_COORDINATOR | Vacant Position | NULL | +91-124-5001209`

### 3.2 Unload Overrun & Dock Capacity Reduction (DEVT003 / SHP1002)
**Finding:** At `FAC-JAI-01`, shipment `SHP1002` checked into `DOCK-JAI-D2` at 08:05, but unload ran significantly longer than planned. Event `DEVT003` records a `CAPACITY_REDUCTION` from 08:00 to 09:20.
```sql
SELECT fc.checkin_id, fc.shipment_id, fc.actual_dock_id, fc.dock_in_ts, fc.queue_state, dse.reason
FROM facility_checkins fc
JOIN dock_status_events dse ON dse.dock_id = fc.actual_dock_id
WHERE fc.actual_dock_id = 'DOCK-JAI-D2';
```
*Actual Output:* `CHK1002 | SHP1002 | DOCK-JAI-D2 | 2026-08-04T08:05:00+05:30 | IN_DOCK | Unload overrun from prior shift reduced turnover speed`

### 3.3 Active Dock Breakdown (DEVT001 / DOCK-JAI-D3)
**Finding:** Hydraulic dock leveller failed at 09:15 on `DOCK-JAI-D3`. Three appointment slots are explicitly marked `BLOCKED`: `SLOT-JAI-031` (10:00-11:00), `SLOT-JAI-032` (11:00-12:00), and `SLOT-JAI-033` (12:00-13:00).
```sql
SELECT slot_id, dock_id, slot_start_ts, slot_end_ts, slot_status, block_reason 
FROM appointment_slots 
WHERE slot_status = 'BLOCKED' AND dock_id = 'DOCK-JAI-D3';
```
*Actual Output:*
- `SLOT-JAI-031 | 10:00 - 11:00 | BLOCKED | Hydraulic leveller breakdown`
- `SLOT-JAI-032 | 11:00 - 12:00 | BLOCKED | Hydraulic leveller breakdown`
- `SLOT-JAI-033 | 12:00 - 13:00 | BLOCKED | Hydraulic leveller breakdown`

### 3.4 Planned Maintenance & Reefer Capacity Exhaustion (DEVT002 / SHP1015)
**Finding:** Reefer dock `DOCK-JAI-D5` has scheduled power maintenance (`DEVT002`) from 18:00 to 22:00. This blocks slots `SLOT-JAI-067` through `SLOT-JAI-070`. Shipment `SHP1015` (dairy products, reefer required) has an updated ETA of 18:30 (`ETA010`). Because the facility closes at 22:00 and no other reefer bay exists at Jaipur DC, **no automated feasible slot exists**, mandating a human escalation.
```sql
SELECT sl.slot_id, sl.dock_id, sl.slot_start_ts, sl.slot_status, sl.block_reason
FROM appointment_slots sl
WHERE sl.dock_id = 'DOCK-JAI-D5' AND sl.slot_start_ts >= '2026-08-04T18:00:00+05:30';
```
*Actual Output:* 4 slots (18:00 to 22:00) all `BLOCKED` with reason `Refrigeration power maintenance`.

### 3.5 Severe Slot Competition at 11:00–12:00 (Standard Docks at Jaipur DC)
**Finding:** At 11:00 AM, five shipments are competing for standard dock capacity:
1. `SHP1009`: CRITICAL priority, 20,000 kg, ETA 10:50 -> Holds `CONFIRMED` on `SLOT-JAI-046` (D4).
2. `SHP1013`: NORMAL priority, 14,000 kg, Low Confidence ETA 11:00 -> Holds `PENDING_CONFIRMATION` on `SLOT-JAI-018` (D2).
3. `SHP1014`: CRITICAL priority, 21,000 kg, ETA 11:25 -> Holds `PENDING_CONFIRMATION` on `SLOT-JAI-004` (D1).
4. `SHP1006`: HIGH priority, 7,800 kg, ETA revised to 11:20 -> Its current slot was 10:00–11:00 (expired/unusable). Needs a slot after 11:20!
5. `SHP1012`: NORMAL priority, 8,000 kg, ETA 11:10 -> Previous slot `APT1012A` was cancelled. Needs a slot, with hard constraint to depart by 13:30!
6. `DOCK-JAI-D3` is `BLOCKED` due to breakdown.
**Result:** From 11:00 to 12:00, standard dock available capacity is exactly 0. The next open slots appear only at 12:00 (`SLOT-JAI-019` on D2 and `SLOT-JAI-047` on D4).

### 3.6 Ambiguous Shipment Assignment for Driver (DRV004 / THR010)
**Finding:** Driver `DRV004` (Sandeep Meena) is assigned to two distinct shipments on 2026-08-04:
- `SHP1004` (ORD-260804-004): Kota -> Jaipur, status `WAITING` in yard.
- `SHP1020` (ORD-260804-020): Kota -> Jaipur, status `ASSIGNED`, departure 13:30.
In thread `THR010`, driver sends: *"I will be late by 45 minutes."*
```sql
SELECT s.shipment_id, s.order_reference, s.current_status, s.planned_departure_ts, s.original_eta_ts
FROM shipments s
WHERE s.driver_id = 'DRV004';
```
*Actual Output:*
- `SHP1004 | ORD-260804-004 | WAITING  | 2026-08-04T03:30:00+05:30 | 2026-08-04T08:45:00+05:30`
- `SHP1020 | ORD-260804-020 | ASSIGNED | 2026-08-04T13:30:00+05:30 | 2026-08-04T18:00:00+05:30`
**Integrity Rule:** The agent must NEVER guess which shipment is delayed. It must ask a focused clarification asking whether the driver is referring to ORD-260804-004 or ORD-260804-020.

### 3.7 Low-Confidence / Range ETA Parsing (SHP1013 & SHP1017)
**Finding:**
- `SHP1013` (THR003): Driver says *"I am late by one hour"*. Recorded as `confidence_code = 'LOW'`.
- `SHP1017` (THR011): Driver declares arrival between 12:30 and 13:00. Recorded as `confidence_code = 'LOW'`.
**Integrity Rule:** Low confidence ETAs require either clarification or conservative scheduling (booking based on the later bound of the window: 13:00), and cannot displace confirmed commitments.

### 3.8 Duplicate Message Deduplication (THR001 / THR009)
**Finding:** Message `MSG015` in `THR009` has `external_message_id = 'wa-9009'` and content identical to `MSG001` (`wa-9001`) from `DRV006`.
```sql
SELECT chat_message_id, thread_id, external_message_id, is_duplicate, message_text 
FROM chat_messages 
WHERE thread_id IN ('THR001','THR009');
```
*Actual Output:* `MSG015` is marked `is_duplicate = 1`. In `driver_exceptions`, both share `dedupe_key = 'DRV006-SHP1006-20260804-0934'`. The system must ignore duplicate retries and avoid duplicate booking attempts.

---

## 4. Summary of Facts, Estimates, Assumptions, & Unknowns

| Category | Item Description | Authority & Evidence |
|---|---|---|
| **Fact** | Database schema, foreign keys, and indexes are fully operational and verified. | SQLite PRAGMA checks and table scans |
| **Fact** | Jaipur DC has 6 docks (4 Standard, 1 Reefer, 1 Heavy); Gurugram has 3 docks. | Table `docks` |
| **Fact** | Reefer dock D5 is unavailable 18:00–22:00 on 2026-08-04. | Table `dock_status_events` (`DEVT002`) |
| **Fact** | D3 hydraulic leveller is broken 09:15–13:00 on 2026-08-04. | Table `dock_status_events` (`DEVT001`) |
| **Fact** | Double bookings are blocked by partial unique index `ux_active_appointment_per_slot`. | Index definition in SQLite |
| **Estimate** | Unload duration for standard loads ranges between 45 and 75 minutes. | Column `shipments.expected_unload_min` |
| **Estimate** | Heavy trailer unload duration requires 90 minutes. | Column `shipments.expected_unload_min` for `SHP1011`, `SHP1016` |
| **Assumption** | Driver chat messages are delivered via an external webhook with a unique `external_message_id`. | Table `chat_messages` structure |
| **Assumption** | Pending warehouse confirmations should auto-expire after 15 minutes if unacknowledged. | Operational workflow assumption |
| **Unknown** | Whether warehouse email delivery failure (`OM004`) was transient or permanent network outage. | Operational message log |
| **Unknown** | Exact GPS location of in-transit trucks (the system operates on declared ETAs, not live telemetry). | Brief & Database Guide Section 1 |
