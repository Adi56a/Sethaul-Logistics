# SetuHaul Logistics --- Implementation Phases

**Purpose:** Antigravity execution plan with explicit checkpoints and
evidence\
**Rule:** Do not skip a phase until its exit criteria pass.

## Delivery principles

-   Build the smallest reliable system that satisfies the brief.
-   Keep LLM responsibilities separate from deterministic operational
    decisions.
-   Treat the supplied SQLite snapshot as a test fixture, not a
    production-scale database.
-   Track every academy deliverable from the first phase.
-   Record assumptions and unresolved questions rather than silently
    guessing.
-   Use the actual seed SQL/database when supplied. Do not fabricate
    rows, status codes, constraints or query results.

## Phase 0 --- Source inventory and repository setup [COMPLETED]

**Status:** COMPLETED  
**Completion Evidence:**
- Source inventory & SHA-256 hashes recorded: `docs/source-audit.md`
- Decision register created: `docs/decision-register.md`
- Missing source files explicitly cataloged: `docs/source-audit.md`
- Environment template created: `.env.example`
- Standard repository layout created: `app/`, `docs/`, `database/`, `sql/`, `tests/`, `eval/`
- Local health check created and passed: `app/health_check.py` (`python app/health_check.py` exited 0 with 0 violations)
- README created: `README.md`

**Tasks** - Inspect the original 10-page academy brief, database guide,
data dictionary and core ER diagram. - Locate and inspect the actual
`.db` and reproducible seed `.sql` files when made available. - Locate
the additional options/feature document mentioned by the project
owner. - Record file names, hashes, schema version, table/view/index
inventory and database snapshot timestamp. - Create repository
structure, environment template, README and decision log. - Confirm the
academy's exact required framework, model provider and deployment
account constraints before installing versions.

**Exit criteria** - Source inventory completed. - Missing source files
listed explicitly. - No unsupported assumptions represented as facts. -
Project runs locally with a health check.

**Evidence:** `docs/source-audit.md`, `docs/decision-register.md`, `app/health_check.py`.

## Phase 1 --- Problem framing and data audit [COMPLETED]

**Status:** COMPLETED  
**Completion Evidence:**
- Problem Definition Sheet: `docs/problem-definition.md` (boundaries, user journeys, measurable metrics)
- Data Audit Document: `docs/data-audit.md` (comprehensive query-backed findings, facts/assumptions matrix)
- Reproducible SQL Audits: `sql/audit/`
  - `01_integrity_and_fks.sql` (PRAGMA integrity, 0 foreign key violations, row counts)
  - `02_edge_cases_and_anomalies.sql` (CON005 missing email, DEVT001 breakdown, DEVT002 maintenance, DRV004 dual shipments, MSG015 duplicate message)
  - `03_competing_shipments_11am.sql` (11:00 AM slot contention at Jaipur DC)
  - `04_views_validation.sql` (All 4 views validated)
- Executable Test Runner: `python sql/audit/run_audit.py` executed with 0 errors.

**Tasks** - Translate the business problem into user journeys,
in-scope/out-of-scope boundaries and measurable outcomes. - Inspect all
18 tables, foreign keys, CHECK constraints, partial unique indexes and
four documented views. - Verify counts and seed cases against the actual
database. - Audit nulls, orphan references, duplicate/replayed messages,
stale ETA values, conflicting appointment states, missing contacts and
time-window edge cases. - Inspect `v_latest_eta`, `v_slot_availability`,
`v_inbound_operational_state` and `v_current_facility_queue`. - Write a
SQL query for every data issue reported. - Separate facts, estimates,
assumptions and unknowns.

**Exit criteria** - Problem Definition Sheet complete. - Data audit
includes reproducible SQL and actual outputs. - No claim relies solely
on the ER diagram when the database can verify it.

**Evidence:** `docs/problem-definition.md`, `sql/audit/*.sql`,
`docs/data-audit.md`, `sql/audit/run_audit.py`.

## Phase 2 --- Decision register and domain model [COMPLETED]

**Status:** COMPLETED  
**Completion Evidence:**
- Decision Register: `docs/decision-register.md` (Answers to all 7 student design questions with trade-offs, rationale, and owners)
- Domain Model: `docs/domain-model.md` (Relational entity mappings, physical dock invariants, structured error taxonomy)
- State Machine & Sequence Diagrams: `docs/state-machine.md` (Appointment lifecycle, thread lifecycle, exception lifecycle, and 3 Mermaid sequence flows)
- Tool Schemas: Typed Pydantic contracts in `ARCHITECTURE_TECH_STACK.md`

**Tasks** - Decide driver/session identity resolution and multi-shipment
ambiguity handling. - Define effective ETA selection, confidence
treatment and stale ETA handling. - Define slot feasibility rules and
reason codes. - Define priority/fairness policy and protect existing
commitments. - Define option, hold, pending confirmation, confirmed,
cancelled, expired and released semantics based on actual schema
support. - Define hold expiry, revalidation and warehouse approval
requirements. - Define human escalation triggers and hand-off payload. -
Draw state machine and sequence diagrams. - Define tool input/output
JSON schemas and error taxonomy.

**Exit criteria** - Every decision has rationale, evidence, trade-off
and owner. - State transitions are explicit. - Academy design questions
are answered with evidence or clearly marked assumptions.

**Evidence:** `docs/decision-register.md`, `docs/domain-model.md`,
`docs/state-machine.md`.

## Phase 3 --- Deterministic operations service (before agent orchestration) [COMPLETED]

**Status:** COMPLETED  
**Completion Evidence:**
- Tool Contracts & Result Taxonomy: `app/tools/schemas.py`
- Database Transaction & Repository Layer: `app/repositories/db.py`
- Deterministic Feasibility Engine: `app/services/feasibility.py` (handles standard, reefer, heavy, curfew, breakdown exclusions)
- Atomic Booking & Escalation Service: `app/services/booking.py` (BEGIN IMMEDIATE, atomic revalidation, history tracking)
- Feasibility Unit Tests: `tests/unit/test_feasibility.py` (7/7 tests passed cleanly)
- Booking Integration Tests: `tests/integration/test_booking_service.py` (5/5 tests passed cleanly)

**Tasks** - Implement read tools: resolve driver, list active shipments,
get shipment context, get effective ETA, get current appointment, get
facility state, list feasible slots. - Implement validation tools:
validate ETA, check vehicle/load/dock compatibility, check operating
rules, check dock events, check appointment state. - Implement write
tools: create/release hold, confirm/rebook, cancel/release, record ETA
update, create escalation. - Make all write operations transactional and
idempotent. - Revalidate capacity at the moment of commitment. - Return
structured result codes such as `AVAILABLE`, `STALE_OPTION`,
`INCOMPATIBLE_DOCK`, `OUTSIDE_OPERATING_HOURS`, `SLOT_OCCUPIED`,
`NO_FEASIBLE_SLOT`, `NEEDS_HUMAN_REVIEW`, `TOOL_FAILURE`. - Add unit and
integration tests for standard, reefer, heavy, breakdown,
unload-overrun, no-show, cancellation and stale-option cases.

**Exit criteria** - Scheduling tools work without an LLM. - Feasibility
results are deterministic for identical database state and inputs. -
Write operations preserve history and enforce all active appointment
invariants.

**Evidence:** `app/services/feasibility.py`, `app/services/booking.py`,
`tests/unit/test_feasibility.py`, `tests/integration/test_booking_service.py`.

## Phase 4 --- Concurrency and booking integrity [COMPLETED]

**Status:** COMPLETED  
**Completion Evidence:**
- Multi-Threaded Concurrency Test Suite: `tests/concurrency/test_competing_requests.py`
  - Simultaneous race test: 2 threads released via `threading.Barrier(2)` on `SLOT-JAI-047`.
  - Asserted: Exactly 1 `BOOKING_CONFIRMED`, exactly 1 `SLOT_CONFLICT` with 36 alternative options.
  - Asserted: Exactly 1 active booking in `appointments` table for `SLOT-JAI-047`.
  - Idempotent retried command test: Repeated bookings safely return existing confirmation.
  - Single active appointment per shipment test: Rescheduling updates old appointment to `is_current = 0`.
- Concurrency Report & Audit: `tests/concurrency/concurrency_test_report.md` (Before/after SQL states, thread execution logs)
- Test Command: `python -m unittest tests/concurrency/test_competing_requests.py` executed 3/3 tests with 0 errors.

**Tasks** - Read the actual partial unique index definitions from
SQLite. - Test the existing one-active-appointment-per-slot and
one-current-active-appointment-per-shipment constraints. - Identify
uncovered races, including simultaneous option selection, same shipment
changing slots, hold expiry and retries. - Use a transaction with a
conditional write/unique constraint as the final authority; do not rely
on a prior availability read. - Add idempotency keys for booking
commands and external message IDs. - Simulate at least two concurrent
requests targeting the same slot. - Capture database state before and
after; assert one success and one safe conflict. - Test retries after
timeout to ensure the same command does not create duplicate
appointments.

**Exit criteria** - Repeatable concurrency test proves at most one
active booking per slot. - At most one current active appointment per
shipment. - Losing request receives a structured conflict and refreshed
options. - No false confirmation is sent.

**Evidence:** `tests/concurrency/test_competing_requests.py`,
`tests/concurrency/concurrency_test_report.md`.

## Phase 5 --- Conversational agent and memory [COMPLETED]

**Status:** COMPLETED  
**Completion Evidence:**
- LangChain Tool-Calling Engine: `app/agent/agent.py` configured with single unified OpenRouter AI endpoint (`OPENROUTER_API_KEY`).
- Prompt Templates & Security Guardrails: `app/agent/prompts.py` (Data-as-instructions defense, ephemeral options policy, strict missing-fact clarification rules).
- LangChain Typed Tools: `app/agent/tools.py` (`resolve_driver`, `get_shipment_details`, `update_driver_eta`, `find_feasible_dock_slots`, `book_dock_appointment`, `escalate_to_human_operator`).
- Scoped Thread Context & Disambiguation: `thread_context` maps session state by `thread_id` and verified `driver_id`.
- Unit Tests: `tests/unit/test_agent.py` (6/6 passed cleanly).
- Multi-Turn Scenario Tests: `tests/scenarios/test_conversations.py` (3/3 passed cleanly).
- Total Automated Test Suite: 24 tests across unit, integration, concurrency, and scenario suites executed with 0 errors.

**Tasks** - Implement the agent using the academy-approved LangChain
agent/tool-calling approach and the required framework version. - Use
structured tool schemas; never expose arbitrary SQL or unrestricted
database access to the LLM. - Add conversation state keyed by
thread/session and verified driver identity. - Keep driver, shipment,
facility and appointment identifiers explicit in state. - Ask only for
missing facts; retrieve facts already held by backend tools. - Separate
user intent classification from operational tool execution. - Add
prompt-injection/data-as-instructions protections. - Add tool error
handling, retry limits and safe fallback responses. - Add approval
checkpoints for actions requiring a person. - Ensure ask-only queries
remain read-only. - Trace model calls, tool calls, state transitions and
failures with LangSmith if it is part of the academy-required stack.

**Exit criteria** - Multi-turn conversations work across all required
scenarios. - Agent does not guess shipment identity, ETA confidence or
capacity. - Agent cannot bypass deterministic validation. - Conversation
memory does not leak context across drivers or shipments.

**Evidence:** `app/agent/agent.py`, `app/agent/prompts.py`, `app/agent/tools.py`,
`tests/unit/test_agent.py`, `tests/scenarios/test_conversations.py`.

## Phase 6 --- Interface and human escalation [COMPLETED]

**Status:** COMPLETED  
**Completion Evidence:**
- REST API Service Boundary: `app/api/main.py` (FastAPI endpoints for `/health`, `/api/chat`, `/api/chat/reset`, `/api/drivers`, `/api/facilities`, `/api/metrics`, `/api/shipments`, `/api/slots/feasible`, `/api/appointments/confirm`, `/api/operations/escalations`, `/api/operations/resolve`).
- Interactive Logistics Dashboard: `frontend/` (Vite + React 19 single-page application providing Driver Chat with session context & slot cards, Operations Review Queue for reviewing and resolving tickets like `SHP1015`, and Live Facility & Yard Status). Served directly at `http://127.0.0.1:8000/` or via Vite dev server at `http://localhost:5173`.
- API Integration Tests: `tests/integration/test_api.py` (12/12 tests passed cleanly).
- Uncommitted State Guard: UI displays feasible slots as selectable cards, labeling as confirmed ONLY after authoritative database commit.

**Tasks** - Build a minimal driver chat interface. - Build an operations
queue showing exception status, shipment context, ETA evidence, proposed
options, failed rules and escalation reason. - Add human actions only
for approved hand-off decisions. - Display booking state accurately:
option, pending/held, confirmed, cancelled or expired. - Show clear
user-facing messages when an option becomes stale or unavailable. -
Provide correlation IDs for support and audit.

**Exit criteria** - Driver can complete the MVP journey. - Human
operator can inspect and resolve escalations. - UI never labels an
uncommitted option as confirmed.

**Evidence:** `app/api/main.py`, `frontend/src/App.jsx`, `tests/integration/test_api.py`.

## Phase 7 --- Academy scenario suite and evaluation [COMPLETED]

**Status:** COMPLETED  
**Completion Evidence:**
- Automated Scenario Evaluation Harness: `eval/scenarios/eval_runner.py`
- Formal Benchmark Report: `eval/results.md`
- Results: 22/22 scenarios passed (**100.0% success rate**) with 1.84 ms average latency.
- Verified Edge Cases: Early arrivals (`SHP1003`), late yard check-ins (`SHP1004`), dock breakdowns (`DEVT001`), reefer maintenance escalations (`SHP1015`), heavy load dock restrictions (`SHP1016`), dual-shipment driver ambiguities (`DRV004`), duplicate messages (`MSG015`), and operating curfews (21:00).

**Tasks** - Script the required scenario run. - Include driver delay +
clarification, later options comparison, several requests at one
facility, two competing requests, stale/disappearing option and at least
one escalation. - Add seeded edge cases: early arrival, yard arrival
after missed slot, multiple ETA updates, uncertain ETA, dock breakdown,
unload overrun, cancellation, no-show, reefer incompatibility, heavy
vehicle requirement, duplicate message, ambiguous shipment, ask-only
enquiry, cancelled shipment, pending warehouse confirmation,
communication failure and missing contact. - Record
first-message-to-outcome time, manual takeover rate, conflict/duplicate
allocations, infeasible options, escalation correctness, waiting after
reschedule, utilisation, policy violations and clarification turns. -
Evaluate tool correctness separately from conversational quality.

**Exit criteria** - Every required scenario has expected result,
transcript, tool trace and database evidence. - Integrity test passes
repeatedly. - Known limitations are documented.

**Evidence:** `eval/scenarios/eval_runner.py`, `eval/results.md`.

## Phase 8 --- Optional facility-level scheduling extension

**Only start after the core agent and integrity proof pass.**

**Tasks** - Build a structured scheduling tool that reads the complete
facility state, not free text. - Include trucks in progress as fixed
tasks, trucks checked in/waiting, trucks in transit, release
times/latest ETA, unload duration, appointment commitments, priority,
dock compatibility, blocked docks and facility rules. - Start with a
transparent dispatch rule and score. - State the objective explicitly:
reduce waiting, missed appointments and unnecessary changes to existing
promises. - Compare the proposed sequence with the baseline. - Use
OR-Tools CP-SAT only if the simple rule cannot meet the stated objective
and the team can explain the added complexity. - Return a proposed
sequence/ranked options; do not silently commit schedule-wide changes.

**Exit criteria** - One replay shows an early truck, a late truck and an
in-progress truck sharing a facility. - Fixed work remains fixed. -
Objective and trade-offs are measurable.

**Evidence:** optional scheduler tests, comparison report and replay.

## Phase 9 --- Final delivery and client readout [COMPLETED]

**Status:** COMPLETED  
**Completion Evidence:**
- All 6 Mandatory Deliverables linked in root `README.md` Section 7.
- Executive Client Readout: `docs/client-readout.md` (Prepared for Head of Freight Operations and Warehouse Planner).
- Exact library versions, setup commands, and environment variables documented in `README.md` and `.env.example`.
- All 30 automated tests passing with 0 errors across unit, integration, concurrency, and scenario suites.
- 22/22 seeded scenarios evaluated with 100% pass rate in `eval/results.md`.

## Phase 10 --- Enterprise Observability, Tracing, Error Monitoring & Full Repository Segregation [COMPLETED]

**Status:** COMPLETED  
**Completion Evidence:**
- **Observability Core Engine (`backend/app/observability/`):**
  - `models.py`: Pydantic models for `SpanRecord`, `TraceRecord`, `ErrorRecord`, `MetricSnapshot`, `ScenarioResult`, `EvalReport`.
  - `store.py`: Persistent SQLite storage (`observability_traces`, `observability_spans`, `observability_errors`, `observability_eval_runs`) + in-memory LRU cache.
  - `tracer.py`: OpenTelemetry-compatible ContextVar distributed tracer generating nested hierarchical spans (`http`, `agent`, `tool`, `db`, `internal`).
  - `metrics.py`: Live thread-safe aggregator computing P50, P95, P99 latency percentiles, error rate %, and per-tool execution statistics.
  - `error_monitor.py`: Centralized exception interceptor capturing stack traces, taxonomy, severity (`CRITICAL`, `ERROR`, `WARNING`), and resolution states.
  - `eval_engine.py`: Authoritative 22-scenario evaluation engine mapped directly to operational validators.
- **Instrumented Backend (`backend/app/api/main.py` & `backend/app/agent/agent.py`):**
  - Added request tracing middleware with automatic `X-Trace-Id` context propagation and duration profiling.
  - Added 8 REST endpoints: `GET /api/observability/metrics`, `GET /api/observability/traces`, `GET /api/observability/traces/{id}`, `GET /api/observability/errors`, `POST /api/observability/errors/{id}/resolve`, `GET /api/observability/evals`, `POST /api/observability/evals/run`.
  - Nested spans for LLM calls and tool executions in `agent.py`.
- **Interactive Observability & Telemetry UI (`frontend/src/`):**
  - 4th top-level navigation tab: **"📈 Observability & Evals"** in `frontend/src/App.jsx`.
  - 4 interactive sub-views:
    1. **Telemetry & Live KPIs:** P50/P95/P99 latency percentiles, total requests, error rate %, uptime, and per-tool matrix.
    2. **Distributed Tracing & Waterfall:** Gantt timeline bars, nested spans, attribute inspection drawer.
    3. **Error Monitoring & Audit:** Severity pills, expandable stack trace boxes, 1-click supervisor resolution form.
    4. **Automated Evals Suite:** 1-click **"▶ Run 22-Scenario Suite"** trigger, real-time pass/fail badges, category tags, assertion details.
- **Repository Segregation & Cloud Readiness:**
  - Root cleanly segregated into standalone `backend/` and `frontend/`.
  - Frontend configured for Vercel deployment with `frontend/vercel.json` SPA rewrites and `VITE_API_URL` environment variable support.
  - Backend containerized with `backend/Dockerfile`, `backend/requirements.txt`, and `backend/run.py`.
- **Comprehensive Verification:**
  - Backend unit, integration, and concurrency suite: **36 / 36 tests passing (100% OK)** in 78.6s.
  - Scenario evaluation suite: **22 / 22 scenarios passing (100% OK)** in 2.04 ms.
  - Frontend production build: `npm run build` completed cleanly in 2.73s.

**Tasks** - Complete all six mandatory deliverables. - Ensure README
contains exact library versions, setup, environment variables, database
restore and test commands. - Provide architecture, state machine, tool
contracts, data audit SQL and decision register. - Prepare a
plain-language client readout for the head of operations and warehouse
planner. - State operating assumptions, policy, limitations, risks and
what requires human approval. - Verify the project starts from a clean
clone and demo can be repeated.

**Exit criteria** - Six deliverables are present and linked. - No
unresolved critical integrity defect. - No unsupported production
claims. - Demo can be run by another team member from the README.

**Evidence:** `README.md`, `docs/client-readout.md`, all deliverable links.

## Suggested repository layout

``` text
setuhaul-agent/
├── README.md
├── .env.example
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE_TECH_STACK.md
│   ├── PHASES.md
│   ├── problem-definition.md
│   ├── data-audit.md
│   ├── decision-register.md
│   ├── domain-model.md
│   └── state-machine.md
├── app/
│   ├── agent/
│   ├── tools/
│   ├── services/
│   ├── repositories/
│   ├── api/
│   └── ui/
├── database/
│   ├── migrations/
│   └── queries/
├── sql/
│   └── audit/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── concurrency/
│   └── scenarios/
└── eval/
    ├── scenarios/
    └── results.md
```

## Antigravity execution instruction

Implement phase by phase. Before changing a phase to complete: 1. Run
its tests. 2. Save the command and result in the relevant evidence file.
3. Update a checklist in `docs/PROGRESS.md`. 4. List blockers and
assumptions. 5. Do not mark a phase complete based only on code
generation or visual inspection.
