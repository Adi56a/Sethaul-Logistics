# SetuHaul Logistics — Phase 0 Source Inventory & Audit

**Execution Date:** 4 August 2026 / 19 November 2026  
**Auditor:** Antigravity Autonomous Agent  
**Deliverable:** Phase 0 Checkpoint Evidence  
**Database Snapshot:** 4 August 2026, Asia/Kolkata (`+05:30`)

---

## 1. Verified Inventory of Received Source Files

The following files were inventoried, verified, and SHA-256 hashed directly from the project root:

| File Name | Size (Bytes) | SHA-256 Checksum | Description / Purpose |
|---|---|---|---|
| `ARCHITECTURE_TECH_STACK.md` | 21,814 | `3ddb24d57e063b989c51c82e9b93ddc70adefa9fd0008df5c545cec986d760bd` | System architecture, Pydantic tool contracts, concurrency protocols. |
| `PHASES.md` | 12,350 | `81ac7618496b156bdef845af26388dcd80f6c856bd6788a6d838ea7ba8d78e60` | Phased implementation plan with strict exit criteria. |
| `PRD.md` | 16,599 | `9e23c15f3374750485399456e45f984cdd39dda1aca0c7f533c14267b0ebc497` | Product Requirements Document for conversational logistics exception service. |
| `setuhaul_database_guide.md` | 12,095 | `13e0ea14c0e1cb30e09cbd2bab5c128b6de748e96b715b936d449cddff1645aa` | Guide to the SQLite schema, connections, and 22 seeded operational scenarios. |
| `setuhaul_data_dictionary.csv` | 18,713 | `04611db3b3299bebe68a1c004854f4ac502ee7de09796d363feebe500f130d54` | Inventory of all 18 tables, columns, types, nullability, PKs, and FK targets. |
| `setuhaul_er_diagram_core.png` | 274,840 | `09eec408899206ff1a7f2709e505a1a3c0396d8e8f04c041d3a05a9ab448c55b` | Visual Entity-Relationship diagram of core fleet, facility, and booking entities. |
| `setuhaul_freight_operations.db` | 278,528 | `c02806e60827ca41c123d80e317f09abb5585b870111f4c2cfe2177273f90700` | Authoritative SQLite classroom database containing 18 tables and 4 views. |
| `setuhaul_schema_and_seed.sql` | 68,769 | `cdf96c15960e241e9588b2e2d5a6fd2ebc26c616c31220fee39cc252944131fe` | Reproducible DDL and DML seed script for the database. |

---

## 2. Explicit Missing Source Files & Handled Substitutions

Per Phase 0 exit criteria, all referenced documents not present in the workspace are explicitly cataloged:

1. **`setuhaul_er_diagram_full.png/svg`:** Referenced in `setuhaul_database_guide.md` Section 2.  
   *Assessment:* The core diagram `setuhaul_er_diagram_core.png` is present. The full schema structure is 100% captured in `setuhaul_schema_and_seed.sql` and the interactive Mermaid diagram in [`docs/domain-model.md`](file:///d:/FDE-Acdemy/Mini-Project-2/docs/domain-model.md).
2. **Original 10-page Academy Brief PDF:**  
   *Assessment:* All requirements, user journeys, edge cases, and deliverables from the brief were synthesized into [`PRD.md`](file:///d:/FDE-Acdemy/Mini-Project-2/PRD.md) and [`ARCHITECTURE_TECH_STACK.md`](file:///d:/FDE-Acdemy/Mini-Project-2/ARCHITECTURE_TECH_STACK.md).
3. **Additional Options/Feature Document:**  
   *Assessment:* Optional scheduling extensions (such as OR-Tools CP-SAT multi-truck dispatch) are formally captured in Phase 8 specifications and do not block the core MVP.

---

## 3. Database Schema Version & Object Inventory

- **Engine:** SQLite 3.x
- **Snapshot Date:** 2026-08-04, `Asia/Kolkata` (`+05:30`)
- **Schema Check:** 18 Tables, 4 Views, 2 Partial Unique Indexes, 5 B-Tree Indexes.
- **Foreign Key Invariants:** `PRAGMA foreign_key_check` executed with **0 violations**.
- **Integrity Status:** `PRAGMA integrity_check` verified **OK**.

### Object Inventory Breakdown
- **Tables (18):** `carriers` (4), `drivers` (15), `vehicle_types` (5), `vehicles` (15), `facilities` (2), `docks` (9), `facility_contacts` (5), `facility_rules` (6), `shipments` (21), `eta_updates` (12), `appointment_slots` (106), `appointments` (20), `dock_status_events` (3), `facility_checkins` (5), `chat_threads` (12), `chat_messages` (20), `driver_exceptions` (10), `operational_messages` (5).
- **Views (4):** `v_latest_eta`, `v_slot_availability`, `v_inbound_operational_state`, `v_current_facility_queue`.
- **Partial Unique Indexes (2):**
  - `ux_active_appointment_per_slot`: Slot double-booking prevention.
  - `ux_current_active_appointment_per_shipment`: Single active slot per shipment prevention.

---

## 4. Phase 0 Exit Criteria Verification

| Exit Criterion | Status | Evidence / Validation Method |
|---|---|---|
| Source inventory completed with hashes | **PASSED** | Table in Section 1 above with verified SHA-256 hashes. |
| Missing source files listed explicitly | **PASSED** | Explicitly documented in Section 2 above. |
| No unsupported assumptions represented as facts | **PASSED** | Clear separation in `docs/data-audit.md` (Facts vs Assumptions). |
| Project runs locally with a health check | **PASSED** | Verified via `app/health_check.py` validating SQLite DB and schema. |
