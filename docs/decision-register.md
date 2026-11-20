# SetuHaul Logistics — Architecture & Policy Decision Register

**Project:** FDE Academy Mini Project 2  
**Document Status:** Approved Architecture Decisions  
**Operational Date:** 4 August 2026, Asia/Kolkata (`+05:30`)

---

## 1. Architectural Principles

1. **LLM Coordinates, Deterministic Services Decide:**  
   The Large Language Model is strictly confined to natural language understanding (intent recognition, entity extraction), driver communication (empathy, clarity, concise questions), and explaining structured decisions. The LLM is NEVER granted authority to calculate capacity, evaluate dock compatibility, execute arbitrary SQL, or commit bookings.
2. **Deterministic Feasibility & Booking Engine:**  
   All dock compatibility checks, ETA calculations, operating window validations, slot reservations, and priority ranking are executed by pure Python domain code and transactional SQL queries.
3. **Database as Final Arbiter of Concurrency:**  
   Capacity locks and anti-double-booking guarantees are enforced at the database layer via partial unique indexes (`ux_active_appointment_per_slot` and `ux_current_active_appointment_per_shipment`) wrapped in `BEGIN IMMEDIATE` SQLite transactions.

---

## 2. Answers to the 7 Academy Student Design Questions

### Decision ADR-01: Clarification Boundaries Before Calling Scheduling Tools
- **Question:** Which information should the agent clarify before calling any scheduling tool?
- **Decision:** The agent clarifies ONLY:
  1. **Shipment Disambiguation:** If the verified driver identity is associated with more than one active shipment (e.g. `DRV004` associated with `SHP1004` and `SHP1020`), the agent MUST ask which shipment the driver is referring to before checking slots.
  2. **Arrival Time / Window:** If the delay message is ambiguous or relative without an anchor (e.g. *"late by one hour"* without specifying whether it's 1 hour after current slot start or 1 hour from now), the agent asks for the estimated clock time of arrival.
  3. **Hard Downstream Constraints:** Genuinely missing constraints (such as a hard departure deadline, e.g., *"must leave by 13:30"*).
- **Negative Boundary:** The agent MUST NOT ask for information already present in authoritative systems (origin, carrier, vehicle registration, cargo type, load weight, or current appointment slot).
- **Evidence:** Table `chat_messages` (MSG006, MSG017).

### Decision ADR-02: Ephemeral Option Display vs Capacity Reservation
- **Question:** Should a displayed option reserve capacity, or should capacity change only after explicit driver confirmation?
- **Decision:** Displayed options are strictly **ephemeral (read-only queries)**. Displaying options does NOT create a hold or reserve a slot.
- **Rationale:** Creating temporary reservations whenever an agent lists options creates a severe Denial-of-Service vector: drivers casually querying available times would lock out arriving trucks. Capacity changes ONLY when the driver explicitly chooses an option.
- **Trade-off:** A slot shown to Driver A may be booked by Driver B before Driver A confirms. To handle this cleanly, the booking tool performs an atomic re-validation upon selection; if the slot was taken in the interim, it returns `SLOT_CONFLICT`, immediately presents fresh alternatives, and explains the situation transparently.
- **Evidence:** PRD FR-09, FR-10; Journey B & C.

### Decision ADR-03: Concurrent Booking Race Resolution
- **Question:** How should the system handle two drivers choosing the same slot at nearly the same time?
- **Decision:** The system utilizes an atomic conditional write inside a `BEGIN IMMEDIATE` transaction, protected by the SQLite partial unique index `ux_active_appointment_per_slot`.
- **Workflow:**
  1. Transaction 1 wins the lock, updates the appointment record, and successfully commits.
  2. Transaction 2 encounters a `sqlite3.IntegrityError: UNIQUE constraint failed: appointments.slot_id`.
  3. The backend catches this error, safely rolls back Transaction 2, and returns a structured response `{ "status": "SLOT_CONFLICT", "slot_id": "...", "reason": "Capacity already claimed by a competing request" }`.
  4. The agent informs Driver 2 that the slot was just claimed, retrieves the next best available feasible options, and prompts Driver 2 to select from the refreshed list.
- **Evidence:** `tests/concurrency/test_competing_requests.py`.

### Decision ADR-04: Priority, Physical Presence, Waiting Time, and Commitment Balance
- **Question:** How should priority, physical arrival, waiting time, and appointment commitments be balanced?
- **Decision:** We establish a 4-tier deterministic decision hierarchy:
  1. **Tier 1 — Commitment Protection (Non-Negotiable):** A confirmed, on-time appointment (`CONFIRMED` or `IN_PROGRESS`) for an arriving truck is NEVER autonomously displaced or revoked by an in-transit truck, regardless of the in-transit truck's priority. Displacement of committed slots requires human manager approval.
  2. **Tier 2 — Safety & Physical Feasibility (Hard Gates):** Compatible dock type (Standard, Reefer, Heavy), vehicle weight $\le$ dock max weight, slot duration $\ge$ expected unload duration, slot start within facility operating hours (before 21:00 at Jaipur), and no active dock breakdown (`dock_status_events`).
  3. **Tier 3 — Yard Presence vs In-Transit Allocation:** When an unallocated or cancelled slot becomes available, a truck already physically waiting in the yard (`queue_state IN ('WAITING_EARLY', 'WAITING_LATE')`) is prioritized over distant in-transit trucks to minimize yard congestion and driver wait time, provided cargo priority is equal or higher.
  4. **Tier 4 — Shipment Priority Tie-Breaker:** For competing unallocated slots among in-transit vehicles: `CRITICAL` > `HIGH` > `NORMAL` > `LOW`. When priorities are identical, the earliest revised ETA wins (First-Come First-Served).
- **Evidence:** `setuhaul_database_guide.md` Section 6, cases SHP1003, SHP1009, SHP1014.

### Decision ADR-05: Expiry of Pending Warehouse Confirmations
- **Question:** When should a pending warehouse confirmation expire?
- **Decision:** Appointments in `PENDING_CONFIRMATION` (e.g. `APT1013A`, `APT1014A`) are governed by a 15-minute Time-To-Live (TTL), or must be confirmed at least 30 minutes before slot start.
- **Workflow:** If warehouse confirmation is not received within the TTL window:
  - If the slot is $\ge 45$ minutes away: the request escalates to the operations queue.
  - If the slot start is imminent ($< 30$ minutes): the pending hold auto-expires (`status = 'REJECTED'` or `'CANCELLED'`), freeing the slot for waiting yard trucks, and the driver is alerted to select a later slot.
- **Evidence:** Table `appointments` statuses, `facility_rules` grace limits.

### Decision ADR-06: Infeasible Compatible Slot Policy & Escalation
- **Question:** What should happen when no feasible compatible slot exists?
- **Decision:** When the feasibility engine returns zero available compatible slots (such as `SHP1015` where reefer dock D5 is under maintenance from 18:00 to 22:00, or when all slots exceed operating hours):
  1. The system creates an escalation record in `driver_exceptions` (`exception_status = 'ESCALATED'`).
  2. It generates an audit payload containing the driver message, shipment ID, cargo requirements, revised ETA, failed dock checks, and reason code `NO_FEASIBLE_SLOT`.
  3. The agent explains to the driver that no automated dock slot is currently available on the schedule, confirms that an operations coordinator has been assigned to the case, and instructs the driver on safe holding/parking procedures without making unauthorized booking promises.
- **Evidence:** Case `SHP1015 / THR005`, `DEVT002`.

### Decision ADR-07: Mandatory Deterministic Validation
- **Question:** Which actions require deterministic validation even if an LLM suggested them?
- **Decision:** ALL writes and operational checks require 100% deterministic code validation:
  - Validating dock type vs shipment temperature / weight requirements.
  - Calculating slot feasibility against latest ETA + unloading duration.
  - Checking dock breakdown and maintenance events.
  - Recording ETA updates in `eta_updates`.
  - Creating or mutating records in `appointments` and `chat_threads`.
  - Triggering human escalations in `driver_exceptions`.

---

## 3. Technical & Operational Decisions

| ADR ID | Decision Area | Chosen Implementation | Alternative Rejected | Justification |
|---|---|---|---|---|
| **ADR-08** | Application Framework | Python + FastAPI + Pydantic v2 | Flask / Django Rest | Strict type schemas, async capabilities, OpenAPI documentation |
| **ADR-09** | Concurrency Protocol | SQLite `BEGIN IMMEDIATE` + busy timeout (5000ms) + Partial Unique Index | Optimistic Locking with version column | Leverages SQLite engine-level write lock and existing classroom index `ux_active_appointment_per_slot` without schema migrations |
| **ADR-10** | Agent Architecture | LangChain Tool-Calling Agent with bounded tools | Autonomous Agent / AutoGPT | Deterministic tool schemas prevent hallucinated SQL and unbounded tool recursion |
| **ADR-11** | Idempotency | `idempotency_key = Hash(driver_id + shipment_id + slot_id + action)` | Blind retries | Prevents duplicate bookings from network retries or duplicate driver messages |
| **ADR-12** | Timezone Standard | ISO-8601 text with explicit `+05:30` offset (Asia/Kolkata) | UTC naive / local system time | Maintains absolute consistency with the seed snapshot timestamps |
