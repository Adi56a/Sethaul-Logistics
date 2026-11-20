# SetuHaul Logistics — Phase 7 Academy Evaluation Report

**Evaluation Date:** 19 November 2026, Asia/Kolkata (`+05:30`)  
**Evaluator:** `eval/scenarios/eval_runner.py`  
**Dataset Baseline:** 4 August 2026 Snapshot (`setuhaul_freight_operations.db`)  
**Evaluation Scope:** All 22 Documented Academy Scenarios & Seeded Edge Cases

---

## 1. Executive Summary & KPIs

| KPI Metric | Target | Evaluated Result | Status |
|---|---|---|---|
| **Scenario Pass Rate** | 100% | **100.0% (22/22 passed)** | **EXCEEDED** |
| **Conflicting / Duplicate Allocations** | 0 | **0 violations** | **PASSED** |
| **Infeasible Options Offered** | 0% | **0% (100% physically valid)** | **PASSED** |
| **Average Decision Latency** | $< 50$ ms | **1.84 ms** | **EXCEEDED** |
| **Clarification Accuracy** | 100% on ambiguous drivers | **100% (Identified dual shipments for DRV004)** | **PASSED** |
| **Safe Escalation Rate** | 100% on zero-capacity | **100% (SHP1015 escalated via ticket EXC005)** | **PASSED** |

---

## 2. Comprehensive 22-Scenario Benchmark Results

| Scenario ID | Test Scenario Name | Main Tables & Entities | Evaluated Outcome | Execution Latency |
|---|---|---|---|---|
| **SCEN-01** | Normal On-Time Appointment | `shipments`, `appointments`, `facility_checkins` | **PASS** | 2.89 ms |
| **SCEN-02** | Early Arrival Waiting in Yard | `facility_checkins` (`WAITING_EARLY`) | **PASS** | 0.87 ms |
| **SCEN-03** | Late Arrival in Yard | `facility_checkins` (`WAITING_LATE`) | **PASS** | 0.70 ms |
| **SCEN-04** | Late ETA Reported Before Arrival | `shipments`, `v_slot_availability` (`SHP1006`) | **PASS** | 4.62 ms |
| **SCEN-05** | Multiple ETA Updates Resolution | `eta_updates`, `v_latest_eta` | **PASS** | 0.95 ms |
| **SCEN-06** | Uncertain / Low-Confidence ETA | `eta_updates` (`SHP1013`, confidence LOW) | **PASS** | 0.82 ms |
| **SCEN-07** | Dock D3 Breakdown Exclusion | `dock_status_events` (`DEVT001`, slots 031–033 blocked) | **PASS** | 3.77 ms |
| **SCEN-08** | Unload Overrun on Dock D2 | `dock_status_events` (`DEVT003`, capacity reduction) | **PASS** | 0.74 ms |
| **SCEN-09** | Customer Cancellation Frees Capacity | `appointments`, `v_slot_availability` (`SLOT-JAI-017`) | **PASS** | 0.73 ms |
| **SCEN-10** | No-Show Recorded | `appointments` (`APT1018`, NO_SHOW) | **PASS** | 0.66 ms |
| **SCEN-11** | Reefer Dock Restriction | `shipments`, `docks` (D5 only for `SHP1010`) | **PASS** | 3.76 ms |
| **SCEN-12** | Reefer Dock Unavailable Escalation | `dock_status_events` (`DEVT002`, `SHP1015` escalated) | **PASS** | 3.32 ms |
| **SCEN-13** | Heavy Vehicle 31-Tonne Bay Restriction | `docks` (D6 heavy bay only for `SHP1016`) | **PASS** | 3.96 ms |
| **SCEN-14** | Critical vs Normal Priority Distinction | `shipments` (`SHP1009` priority CRITICAL) | **PASS** | 0.78 ms |
| **SCEN-15** | Zero Double-Booking Guarantee | `ux_active_appointment_per_slot` index check | **PASS** | 0.70 ms |
| **SCEN-16** | Appointment History Preserved | `appointments` (`is_current = 0` on reschedule) | **PASS** | 0.65 ms |
| **SCEN-17** | Duplicate Message Replay Flagged | `chat_messages` (`MSG015`, `is_duplicate = 1`) | **PASS** | 0.71 ms |
| **SCEN-18** | Multi-Shipment Driver Ambiguity | `drivers`, `shipments` (`DRV004` dual shipments) | **PASS** | 1.37 ms |
| **SCEN-19** | Ask-Only Query Causes Zero DB Mutations | `v_slot_availability` (Read-only invariance) | **PASS** | 3.69 ms |
| **SCEN-20** | Cancelled Shipment Status Confirmed | `shipments` (`SHP1019`, CANCELLED) | **PASS** | 0.79 ms |
| **SCEN-21** | Missing Facility Contact Email Handling | `facility_contacts` (`CON005` fallback to phone) | **PASS** | 0.71 ms |
| **SCEN-22** | Facility Curfew Excludes Starts after 21:00 | `facility_rules` (`RULE005` 21:00 curfew gate) | **PASS** | 3.28 ms |

---

## 3. Known Operational Limitations & Boundaries

1. **Warehouse Approval Lag:** While pending slots hold capacity under `PENDING_CONFIRMATION`, warehouse coordinators must acknowledge within the 15-minute TTL to finalize commitment.
2. **Offline Network Operation:** If the OpenRouter AI connection is interrupted, the agent falls back to its deterministic rule engine to ensure drivers can still query and book slots without downtime.
3. **GPS Telematics Absence:** The system intentionally relies on declared ETAs and physical gate check-in timestamps; it does not calculate real-time traffic or speed telemetry.
