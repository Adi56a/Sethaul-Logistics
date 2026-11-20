# SetuHaul Logistics --- Architecture & Technology Stack

**Architecture principle:** LLM coordinates; deterministic services
decide and commit.\
**Source basis:** FDE Academy project brief, database guide, data
dictionary and supplied core ER diagram.

## 1. Architecture decision

Build a tool-using conversational agent over a deterministic logistics
operations service.

The LLM is responsible for: - Understanding driver intent and
natural-language constraints. - Asking concise clarification
questions. - Selecting approved tools and interpreting their structured
results. - Explaining feasible options and policy outcomes. - Managing
the multi-turn interaction and initiating escalation when required.

The LLM is not responsible for: - Calculating authoritative capacity. -
Deciding dock/vehicle/load compatibility from memory. - Choosing a
booking winner during a race. - Writing arbitrary SQL. - Declaring a
booking confirmed without a successful system-of-record response. -
Approving safety, penalties, compensation or regulated exceptions.

## 2. Logical architecture

``` text
Driver chat UI
     |
     v
API / session boundary
     |
     v
LangChain conversational agent
  - intent + entity extraction
  - conversation state / memory
  - tool selection
  - clarification + response
  - approval / escalation routing
     |
     +------------------------+
     | approved structured tools
     v
Operations application services
  - identity & shipment resolution
  - ETA update service
  - shipment / appointment context
  - feasibility & slot search
  - hold / confirm / release
  - escalation service
     |
     v
Repository / transaction boundary
     |
     v
Supplied SQLite snapshot (MVP)
  - 18 tables
  - 4 documented views
  - foreign keys / CHECK constraints
  - partial unique appointment indexes

Observability:
LangSmith traces + structured application logs + evaluation results

Human operations queue:
escalations, approvals, contradictory data, no-feasible-slot cases
```

For deployment, package the agent service for the academy-required AWS
AgentCore runtime. Keep database and operational services behind
explicit interfaces so the local SQLite classroom setup can be replaced
by a production database later without changing agent prompts/tool
semantics.

## 3. Academy-aligned technology stack

The original project brief specifies capabilities and learning outcomes
rather than naming every library or provider. The stack below is the
proposed implementation mapping. Confirm exact versions and deployment
requirements against the academy course materials before pinning
dependencies.

  -----------------------------------------------------------------------
  Layer                   Proposed technology     Responsibility
  ----------------------- ----------------------- -----------------------
  Agent framework         LangChain tool-calling  Agent loop, structured
                          agent                   tools and model
                                                  interaction

  Model                   Academy-approved LLM    Natural-language
                          provider/model          understanding and
                                                  response

  Tracing/evaluation      LangSmith               Trace prompts, tool
                                                  calls, runs and
                                                  evaluations

  Agent deployment        AWS Bedrock AgentCore,  Managed agent
                          as required by the      runtime/deployment
                          academy track           

  API boundary            Python + FastAPI        Typed HTTP endpoints,
                                                  validation and session
                                                  boundary

  Validation              Pydantic                Strict request/response
                                                  and tool schemas

  Data access             Python `sqlite3` for    Query and transactional
                          supplied SQLite MVP     persistence

  Test framework          pytest                  Unit, integration and
                                                  scenario tests

  Concurrency tests       pytest + multiple       Prove competing booking
                          database                behaviour
                          connections/processes   

  Frontend                React + Vite (proposed) Driver chat and
                                                  operations review UI

  UI API client           fetch/typed client      Communicate with
                                                  FastAPI

  Configuration           environment variables + Secrets and runtime
                          `.env.example` locally  configuration
  -----------------------------------------------------------------------

Do not add LangGraph, a vector database, Redis, Kafka, OR-Tools or a
second database in the MVP unless a documented requirement justifies it.
Conversation state can initially be persisted in the existing
thread/message model or a small application state store, subject to the
actual schema and privacy boundary.

## 4. Data model and source-of-truth mapping

The data dictionary lists 18 tables:

### Parties and fleet

-   `carriers`
-   `drivers`
-   `vehicle_types`
-   `vehicles`

### Facilities and capacity

-   `facilities`
-   `docks`
-   `facility_rules`
-   `appointment_slots`
-   `appointments`
-   `dock_status_events`
-   `facility_contacts`

### Shipment and ETA

-   `shipments`
-   `eta_updates`
-   `facility_checkins`

### Conversation and exceptions

-   `chat_threads`
-   `chat_messages`
-   `driver_exceptions`
-   `operational_messages`

Documented views: - `v_latest_eta` - `v_slot_availability` -
`v_inbound_operational_state` - `v_current_facility_queue`

Use views where their definitions match the tool's purpose, but inspect
their actual SQL before relying on them. Do not infer view columns or
status semantics from their names alone.

## 5. Tool contracts

Expose narrow, typed tools to the agent. Tool names and schemas below
are proposed application contracts; map their fields to the actual
database dictionary.

### Read-only tools

  ---------------------------------------------------------------------------
  Tool                        Input                   Output
  --------------------------- ----------------------- -----------------------
  `resolve_driver_context`    verified driver/session driver identity, active
                              reference               shipment candidates

  `list_driver_shipments`     driver ID, optional     shipment summaries
                              status                  

  `get_shipment_context`      shipment ID             shipment, driver,
                                                      vehicle, destination,
                                                      current status

  `get_effective_eta`         shipment ID             effective ETA, source,
                                                      confidence, timestamp

  `get_current_appointment`   shipment ID             current appointment and
                                                      slot details

  `get_facility_state`        facility ID, time       operating rules, docks,
                              window                  events, queue/check-ins

  `search_feasible_slots`     shipment ID, ETA        ranked feasible options
                              window, constraints     and reason codes

  `validate_slot_option`      shipment ID, slot ID,   current feasibility and
                              decision                stale/conflict result
                              version/context         
  ---------------------------------------------------------------------------

### Write tools

  -----------------------------------------------------------------------------------
  Tool                                Input                   Output
  ----------------------------------- ----------------------- -----------------------
  `record_eta_update`                 shipment, declared ETA, persisted ETA update ID
                                      source, confidence,     and effective ETA
                                      reason                  

  `create_slot_hold`                  shipment, slot,         hold result, expiry,
                                      idempotency key, expiry conflict reason

  `confirm_appointment`               shipment, hold/slot     confirmed appointment
                                      reference, idempotency  or conflict
                                      key                     

  `release_appointment_or_hold`       appointment/hold ID,    resulting state
                                      reason                  

  `create_human_escalation`           thread, shipment,       escalation ID and queue
                                      reason, evidence bundle status

  `record_operational_notification`   shipment, appointment,  notification record
                                      channel, delivery       
                                      result                  
  -----------------------------------------------------------------------------------

### Write tools & Database Mapping

| Tool                          | Input Parameters                                                                                             | Database Mutation & Behavior                                                                                                                                                                                                                                          | Return Schema                                                                            |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `record_eta_update`           | `shipment_id`, `declared_eta_ts`, `source_type`, `confidence_code`, `delay_reason_code`, `note`              | Inserts row into `eta_updates`; updates `shipments.latest_eta_ts`; refreshes view `v_latest_eta`.                                                                                                                                                                     | `{ "eta_update_id": str, "effective_eta_ts": str, "confidence": str }`                   |
| `create_slot_hold`            | `shipment_id`, `slot_id`, `idempotency_key`, `ttl_minutes=15`                                                | Inserts row into `appointments` with `appointment_status = 'PENDING_CONFIRMATION'`, `booking_source = 'DRIVER_CHAT'`, `is_current = 1`. Protected by `ux_active_appointment_per_slot`.                                                                                | `{ "appointment_id": str, "slot_id": str, "status": "HOLD_PENDING", "expires_at": str }` |
| `confirm_appointment`         | `shipment_id`, `slot_id`, `idempotency_key`                                                                  | Executes in `BEGIN IMMEDIATE`. Revalidates feasibility. If slot is open or held by same shipment, sets `appointment_status = 'CONFIRMED'`, `confirmed_at = CURRENT_TIMESTAMP`. Deactivates prior appointment (`is_current = 0, cancellation_reason = 'Rescheduled'`). | `{ "status": "CONFIRMED", "appointment_id": str, "slot_id": str, "dock_code": str }`     |
| `release_appointment_or_hold` | `appointment_id`, `reason`                                                                                   | Sets `appointment_status = 'CANCELLED'` or `'REJECTED'`, `cancelled_at = CURRENT_TIMESTAMP`, `is_current = 0`. Releases slot back to pool.                                                                                                                            | `{ "status": "RELEASED", "appointment_id": str }`                                        |
| `create_human_escalation`     | `thread_id`, `shipment_id`, `driver_id`, `exception_type`, `severity_code`, `description`, `evidence_bundle` | Inserts row into `driver_exceptions` (`exception_status = 'ESCALATED'`); creates notification in `operational_messages`; alerts operations queue.                                                                                                                     | `{ "escalation_id": str, "status": "ESCALATED", "assigned_role": str }`                  |

## 6. Feasibility engine

Implement feasibility as pure deterministic Python domain code backed by SQL queries. It operates independently of LLM reasoning.

For each candidate slot at the destination facility:
1. **Shipment Validation:** Check shipment exists, destination facility matches, and `current_status IN ('PLANNED','ASSIGNED','IN_TRANSIT','WAITING')`.
2. **Dock Compatibility:** 
   - If `temperature_control_required = 1`, require `supports_refrigerated = 1` (Dock D5 at Jaipur).
   - If `load_weight_kg > 25000`, require `dock_type = 'HEAVY'` (Dock D6 at Jaipur).
   - Require `load_weight_kg <= dock.max_vehicle_weight_kg`.
3. **Temporal Feasibility:**
   - Candidate `slot_start_ts >= effective_eta_ts`.
   - Slot duration `(slot_end_ts - slot_start_ts) >= expected_unload_min`.
   - `slot_start_ts` must be $\le$ `LAST_NEW_START_TIME` (21:00 at Jaipur per `RULE005`).
   - Slot must end before facility close time (22:00 at Jaipur).
4. **Dock Availability & Events:**
   - `slot_status` must be `'OPEN'`.
   - No active breakdown or maintenance overlapping the slot in `dock_status_events` (e.g., `DEVT001` on D3, `DEVT002` on D5).
   - No active appointment in `v_slot_availability` (`availability_status == 'AVAILABLE'`).
5. **Ranking:** Feasible slots are ranked by proximity to declared ETA, with earlier feasible slots prioritized.

Structured Feasibility Output Schema:
```json
{
  "shipment_id": "SHP1006",
  "facility_id": "FAC-JAI-01",
  "effective_eta_ts": "2026-08-04T11:20:00+05:30",
  "feasible_slots": [
    {
      "slot_id": "SLOT-JAI-047",
      "dock_code": "D4",
      "dock_type": "STANDARD",
      "slot_start_ts": "2026-08-04T12:00:00+05:30",
      "slot_end_ts": "2026-08-04T13:00:00+05:30",
      "max_weight_kg": 25000,
      "checks_passed": ["DOCK_COMPATIBLE", "ETA_TIMELY", "DURATION_SUFFICIENT", "FACILITY_OPEN", "NO_BREAKDOWN"]
    },
    {
      "slot_id": "SLOT-JAI-019",
      "dock_code": "D2",
      "dock_type": "STANDARD",
      "slot_start_ts": "2026-08-04T12:00:00+05:30",
      "slot_end_ts": "2026-08-04T13:00:00+05:30",
      "max_weight_kg": 25000,
      "checks_passed": ["DOCK_COMPATIBLE", "ETA_TIMELY", "DURATION_SUFFICIENT", "FACILITY_OPEN", "NO_BREAKDOWN"]
    }
  ],
  "evaluated_at": "2026-08-04T09:35:00+05:30"
}
```

## 7. Booking integrity and concurrency protocol

The core safety guarantee is that **two concurrent requests can never book the same slot**.

### The SQLite Concurrency Model
1. **Transaction Isolation:** All capacity mutations execute inside Python `sqlite3` using `BEGIN IMMEDIATE` transactions with a configured busy timeout (`timeout=5000` ms). This acquires SQLite's reserved lock immediately, preventing writer deadlocks.
2. **Double-Booking Prevention:** SQLite's partial unique index `ux_active_appointment_per_slot` guarantees at the storage engine level that only ONE appointment in `('PENDING_CONFIRMATION','CONFIRMED','IN_PROGRESS')` can occupy any `slot_id`.
3. **Single Active Appointment per Shipment:** Enforced by partial unique index `ux_current_active_appointment_per_shipment`.
4. **Race Condition Handling:**
   - Request 1 executes write -> succeeds and commits.
   - Request 2 executes write -> triggers `sqlite3.IntegrityError: UNIQUE constraint failed: appointments.slot_id`.
   - The transaction catches `IntegrityError`, executes `ROLLBACK`, queries remaining feasible slots, and returns `{ "status": "SLOT_CONFLICT", "slot_id": "...", "reason": "Slot claimed by another driver during selection", "alternative_slots": [...] }`.
   - The agent transparently explains the race to Driver 2 and offers the alternatives immediately.
5. **Idempotency Guarantee:** Every booking command receives an `idempotency_key` (derived from `driver_id + shipment_id + slot_id + action`). Retrying an identical message returns the existing commitment without re-executing writes or raising constraint errors.

## 8. Conversation state and memory

Conversation state must be scoped by thread and verified driver
identity. Keep structured facts separate from free-form transcript.

Recommended state fields: - `thread_id` - verified `driver_id` -
selected `shipment_id` (nullable until unambiguous) - `current_intent` -
latest declared ETA and confidence - current appointment reference -
options shown, including slot IDs and data-as-of/version metadata -
selected option - booking/hold state - unresolved clarification fields -
escalation status and reason

Rules: - Never reuse one driver's memory for another driver. - If a
driver has multiple candidate shipments, ask which shipment they mean. -
Re-fetch authoritative values when they may have changed. - Treat stored
conversation summaries as context, not as proof of current capacity. -
Keep ask-only intent read-only. - Clear or close state according to a
documented retention policy.

## 9. Human approval and escalation

Escalate when: - No feasible compatible slot exists. - ETA is too
uncertain for a safe commitment. - Data is contradictory or required
fields are missing from authoritative sources. - Driver safety,
emergency or regulated-load decisions arise. - Penalty, compensation or
customer commitment is requested. - A booking/notification tool fails in
a way that leaves commitment status uncertain. - Warehouse confirmation
is required but not received.

Hand-off payload should include thread, driver, shipment, current
appointment, effective ETA/source/confidence, options considered, failed
feasibility rules, attempted writes, relevant message history and reason
for escalation.

Never tell the driver a warehouse has confirmed if only a notification
was sent. Delivery success and business approval are different states.

## 10. Observability and evaluation

Use LangSmith for model/agent traces if included in the academy stack.
Add application logs with: - `request_id`, `thread_id`, `shipment_id`,
`tool_name` - tool input schema version (avoid logging secrets or
unnecessary personal data) - result code, elapsed time and retry count -
booking state transition - escalation reason - database transaction
outcome

Track the academy measures: - Time from first message to usable
outcome. - Share resolved without manual takeover. - Conflicting or
duplicate allocations. - Options later found infeasible. - No-slot
escalations handled correctly. - Average driver waiting after
rescheduling. - Warehouse slot utilisation. - Priority-policy
violations. - Driver clarification turns.

## 11. Optional scheduling extension

Keep optional facility scheduling separate from the core conversational
agent.

The scheduler receives structured operational state, not free text: -
trucks in progress (fixed tasks) and expected completion times; -
early/late trucks in the yard; - trucks still in transit and their
ETA/release times; - unload duration, appointment commitment and
priority; - dock compatibility and blocked/occupied resources; -
facility rules.

Start with a simple dispatch rule and transparent score. Compare it with
a baseline and state the objective in plain language: reduce waiting,
missed appointments and unnecessary changes to promises already made.
Use OR-Tools CP-SAT only if the simple rule is insufficient and the
added complexity can be justified. Return a proposed sequence; do not
autonomously rewrite all appointments.

## 12. Security and operational safeguards

-   Validate every tool argument with Pydantic.
-   Use parameterized SQL only.
-   Never let the model construct or execute arbitrary SQL.
-   Keep provider keys and AWS credentials server-side.
-   Use least-privilege database and cloud permissions.
-   Verify driver identity before exposing shipment information.
-   Do not log phone numbers, licence numbers or message contents unless
    needed for a justified audit purpose; redact where possible.
-   Treat driver text, database notes and external messages as untrusted
    data, never as system instructions.
-   Bound tool retries and model turns.
-   Fail closed on uncertain booking state; reconcile with the database
    before responding.
-   Keep all timestamps timezone-aware and preserve the snapshot's
    Asia/Kolkata (`+05:30`) semantics.

## 13. Architecture acceptance checklist

-   [ ] LLM has only approved typed tools.
-   [ ] Feasibility is deterministic and independently unit-tested.
-   [ ] Driver/shipment ambiguity triggers clarification.
-   [ ] Ask-only enquiry causes no write.
-   [ ] Option display is not treated as a hold.
-   [ ] Confirmation revalidates and writes atomically.
-   [ ] Database constraints are inspected and tested.
-   [ ] Concurrent requests cannot double-book.
-   [ ] Duplicate messages/commands are idempotent.
-   [ ] Stale options return a structured conflict.
-   [ ] Human escalation captures the full evidence bundle.
-   [ ] LangSmith traces and scenario metrics are captured.
-   [ ] README documents exact dependency versions and reproducible
    setup.
