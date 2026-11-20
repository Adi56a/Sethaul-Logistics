# SetuHaul Logistics --- Product Requirements Document

**Project:** FDE Academy Mini Project 2\
**Document status:** Build specification\
**Operational data snapshot:** 4 August 2026, Asia/Kolkata

## 1. Product vision

Build a conversational logistics exception service that helps truck
drivers resolve late-arrival and dock-appointment problems through
natural language. The system must understand the driver's message,
retrieve authoritative operational context, clarify only missing
information, find feasible alternatives, and safely manage appointment
changes.

The product is not an unrestricted chatbot and must not allow an LLM to
invent capacity or make booking commitments. The agent coordinates the
conversation; deterministic services own feasibility and booking
integrity.

## 2. Business context

SetuHaul Logistics Pvt. Ltd. is a third-party full-truckload logistics
operator across North and West India. It coordinates company-owned and
contracted vehicles delivering to factories, warehouses and distribution
centres.

The supplied operating profile describes: - 280--360 loads per day. - 6
facilities and 32 dock doors in the operating profile. - 190--240
receiving appointments per day. - 15--25 ETA updates per day. - 20--35
messages during a 30-minute disruption spike. - 5--25 daily dock
breakdowns, maintenance or capacity events (as shown in the brief's
operating-profile graphic; validate exact interpretation before using as
a KPI).

These are design-scale figures, not the size of the classroom database.
The supplied SQLite snapshot contains 2 facilities, 9 docks and 21
shipments.

## 3. Problem statement

A truck may miss its planned dock appointment because of breakdowns,
traffic, rain, loading backlog or other disruptions. The driver
communicates the delay in natural language, often with incomplete or
imprecise information. The original slot may no longer be feasible, and
several drivers may request the same limited replacement capacity at
nearly the same time.

Manual coordination becomes slow and error-prone. A system that merely
lists open slots is insufficient: availability must be checked against
vehicle/load compatibility, ETA, unloading duration, operating rules,
dock events, current bookings and competing requests. A slot shown to
one driver may become unavailable before the driver confirms it.

## 4. Product goals

1.  Resolve common delay exceptions through a short, context-aware
    conversation.
2.  Ask only for facts that are genuinely missing from authoritative
    systems.
3.  Retrieve shipment, driver, vehicle, ETA, facility, appointment and
    dock context using structured tools.
4.  Return only feasible appointment options, with clear reasons and
    confidence/limitations.
5.  Prevent duplicate or conflicting commitments under concurrent
    requests.
6.  Revalidate any selected option before booking.
7.  Escalate unsafe, contradictory, policy-sensitive or infeasible cases
    to a human with a complete hand-off record.
8.  Produce observable, testable evidence for every important decision.

## 5. Non-goals and boundaries

Out of scope: - National transport-network optimisation. - Carrier
selection and freight-rate negotiation. - Autonomous driver-safety
decisions. - Customs, hazardous-material and legal workflows. -
Autonomous approval of penalties, compensation or commercial
commitments.

The agent never decides alone: - Whether two drivers may be promised the
same capacity. - Whether a vehicle fits a dock. - How scarce capacity is
ranked when policy conflicts. - Whether a booking has been committed in
the system of record.

A person approves or takes over: - Driver safety decisions. - Penalties,
compensation and customer commitments. - Cases with no feasible slot. -
Contradictory data, regulated loads and emergencies.

## 6. Primary users and interfaces

### Primary user: truck driver

Needs to report a delay, clarify an ETA, ask about later/earlier
options, compare choices, accept or reject an option, and receive a
clear confirmation or escalation message.

### Operations / warehouse coordinator

Needs visibility into the exception, shipment and appointment context,
tool results, booking state, reason for escalation and actions still
requiring human approval.

### MVP interface

Implement a simple driver chat interface and an operations view for
reviewing escalations and appointment state. Keep the interface
deliberately small; the academy evaluates the reliability of the agent
and tools, not decorative dashboard complexity.

## 7. Core user journeys

### Journey A --- delay report and reschedule

1.  Driver says they will be late.
2.  Agent identifies the driver and shipment from trusted
    conversation/session context where possible.
3.  If the driver has multiple active shipments or identity is
    ambiguous, ask a focused clarification; do not guess.
4.  Retrieve the current shipment, appointment, latest ETA, facility and
    vehicle context.
5.  Ask only for missing details, such as revised ETA or uncertainty
    range.
6.  Save the ETA update with its source and confidence.
7.  Call the deterministic feasibility/search tool.
8.  Present ranked feasible options and explain relevant trade-offs.
9.  Driver selects an option.
10. Revalidate and attempt an atomic hold/booking transition.
11. Confirm only after the system of record reports success. Otherwise
    explain that the option changed and fetch alternatives.

### Journey B --- ask-only availability enquiry

A driver may ask what options exist without requesting a booking. The
agent must not create a hold or change an appointment merely because it
displayed options.

### Journey C --- stale or unavailable option

If an option has changed, expired, been blocked or been taken by another
driver, do not promise it. Explain the change, refresh the options and
ask the driver how to proceed.

### Journey D --- escalation

When no safe/feasible automatic outcome exists, create an escalation
record containing the conversation, shipment, ETA evidence, attempted
options, rule failures and reason for hand-off. Tell the driver what
happens next without making an unsupported promise.

## 8. Functional requirements

  --------------------------------------------------------------------------
  ID                      Requirement             Acceptance evidence
  ----------------------- ----------------------- --------------------------
  FR-01                   Accept natural-language Demonstration with
                          driver messages         colloquial delay messages

  FR-02                   Identify driver and     Ambiguous-shipment test
                          shipment safely         asks clarification

  FR-03                   Retrieve authoritative  Tool output trace and
                          shipment and            scenario transcript
                          appointment context     

  FR-04                   Distinguish original    Latest-effective-ETA test
                          ETA from later ETA      
                          updates                 

  FR-05                   Ask only for missing    Transcript and
                          information             clarification-turn count

  FR-06                   Parse approximate/range Uncertain ETA scenario;
                          ETAs and record         low confidence escalates
                          uncertainty             or uses conservative
                                                  policy

  FR-07                   Search compatible       Deterministic tool tests
                          feasible slots          across standard, reefer
                                                  and heavy cases

  FR-08                   Explain why options are Rule-level reason codes
                          unavailable or rejected 

  FR-09                   Keep ask-only enquiries Test verifies no
                          read-only               appointment mutation

  FR-10                   Revalidate selected     Stale-option replay test
                          option before           
                          commitment              

  FR-11                   Atomically protect      Competing-request
                          booking transitions     integrity test

  FR-12                   Preserve appointment    Replacement/cancellation
                          history                 history test

  FR-13                   Deduplicate retried     Duplicate-message replay
                          messages/events         test

  FR-14                   Escalate defined cases  At least one recorded
                          to a human              escalation

  FR-15                   Keep an auditable       Correlated logs and state
                          event/decision trail    transitions
  --------------------------------------------------------------------------

## 9. Feasibility rules

The deterministic scheduling engine evaluates candidate slots against operational facts:
1. **Destination Facility & Local Timezone:** Matches destination facility (`FAC-JAI-01` or `FAC-GGN-01`) evaluated strictly in `Asia/Kolkata` (`+05:30`).
2. **Dock Type & Capability Compatibility:**
   - Temperature-controlled loads (`temperature_control_required = 1` or `required_dock_type = 'REEFER'`) MUST use refrigerated docks (`supports_refrigerated = 1`, e.g., Dock D5 at Jaipur DC per `RULE003`).
   - Heavy loads (`load_weight_kg > 25000` per `RULE004`) MUST use heavy bays (`dock_type = 'HEAVY'`, e.g., Dock D6 at Jaipur DC).
   - Cargo weight must not exceed `docks.max_vehicle_weight_kg`.
3. **Unloading Duration vs. Slot Window:** Slot duration (`slot_end_ts - slot_start_ts`) must be $\ge$ `shipment.expected_unload_min` (e.g., standard 45–75 min; heavy 90 min).
4. **Temporal Feasibility:** `slot_start_ts` $\ge$ shipment's latest `effective_eta_ts`.
5. **Operating Hours & Curfew:** Unloading must start before `facility_rules.LAST_NEW_START_TIME` (21:00 at Jaipur DC per `RULE005`) and finish before facility close time (22:00).
6. **Dock Status Events & Maintenance:** Slots overlapping active breakdown or maintenance events (`dock_status_events`, e.g., `DEVT001` leveller breakdown on D3, `DEVT002` maintenance on D5) are classified as `BLOCKED` and excluded.
7. **Active Booking Conflict Check:** The slot must not have an active booking (`PENDING_CONFIRMATION`, `CONFIRMED`, `IN_PROGRESS`) in `v_slot_availability`.
8. **Yard State Awareness:** Physical arrival status from `facility_checkins` is integrated into allocation scoring.

## 10. Appointment lifecycle

The application lifecycle strictly respects the database schema CHECK constraint:
`CHECK (appointment_status IN ('PENDING_CONFIRMATION','CONFIRMED','IN_PROGRESS','COMPLETED','CANCELLED','NO_SHOW','REJECTED'))`

1. **Option Display (`OPTION_DISPLAYED`):**
   - Strictly ephemeral in agent memory.
   - Read-only; does NOT create an appointment record or hold database capacity.
2. **Pending Hold / Warehouse Approval (`PENDING_CONFIRMATION`):**
   - Active database record (`is_current = 1`).
   - Protected by `ux_active_appointment_per_slot`.
   - Governed by a 15-minute Time-To-Live (TTL). If unconfirmed within TTL or 30 minutes before slot start, transitions to `REJECTED` or `CANCELLED`.
3. **Confirmed Commitment (`CONFIRMED`):**
   - Authoritative commitment committed inside an atomic `BEGIN IMMEDIATE` transaction.
   - Sets `confirmed_at = CURRENT_TIMESTAMP`.
   - If replacing an earlier appointment, marks old appointment `is_current = 0, cancellation_reason = 'Rescheduled'`.
   - Driver confirmation message is dispatched ONLY after the database transaction successfully commits.
4. **Execution & Terminal States:**
   - `IN_PROGRESS`: Truck enters bay (`facility_checkins.queue_state = 'IN_DOCK'`).
   - `COMPLETED`: Unloading finished and truck departs.
   - `CANCELLED`: Released by customer cancellation or rescheduled.
   - `NO_SHOW`: Truck fails to check in within grace period (30 min at Jaipur DC per `RULE002`).
   - `REJECTED`: Warehouse or driver rejected pending option, or hold expired.

## 11. Decision policy

To ensure transparency, reliability, and fairness, the system adheres to a 4-tier decision hierarchy:
1. **Tier 1 — Commitment Protection (Non-Negotiable):**
   A confirmed, on-time appointment (`CONFIRMED` or `IN_PROGRESS`) is NEVER autonomously bumped or cancelled to accommodate an in-transit truck, regardless of the in-transit truck's priority. Displacing committed appointments requires human operations supervisor authorization.
2. **Tier 2 — Physical Feasibility & Safety Hard Gates:**
   Slots must strictly pass all physical constraints (dock type, vehicle weight limit, unloading duration, facility open hours, and dock status breakdown events). No automated override is permitted.
3. **Tier 3 — Physical Yard Presence vs. In-Transit:**
   When an open or cancelled slot becomes available, trucks physically waiting in the facility yard (`facility_checkins.queue_state IN ('WAITING_EARLY', 'WAITING_LATE')`) receive precedence over distant in-transit trucks with equal priority, reducing yard congestion and driver dwell time.
4. **Tier 4 — Shipment Priority & Arrival Tie-Breaker:**
   When competing for unallocated capacity:
   - Priority code rank: `CRITICAL` > `HIGH` > `NORMAL` > `LOW`.
   - For identical priority levels, the truck with the earlier declared ETA receives preference (First-Come, First-Served).
   - Low-confidence or range ETAs are scheduled against the conservative (later) bound of the window and flagged for operator review if capacity is constrained.

## 12. Required academy deliverables

1.  **Problem Definition Sheet + data audit:** separate facts,
    estimates, assumptions and unknowns; every reported data issue must
    have a query proving it.
2.  **Decision register:** each important design decision, rationale and
    evidence.
3.  **Working prototype:** conversation layer, tools and state; README
    must name library versions.
4.  **Scenario run:** scripted or recorded demonstration of the required
    scenarios, ending in at least one escalation.
5.  **Integrity proof:** competing requests for the same slot with
    evidence that no double-booking occurs.
6.  **Client readout:** plain-language note for the head of operations
    and warehouse planner covering policy, limits and open risks.

Required scenario run must show: - Driver reports a delay and answers
clarification questions. - Driver asks for later options and compares
them. - Several requests run against the same facility schedule. - At
least two requests compete for the same capacity. - Driver sees what
happens when an option changes or disappears. - At least one case ends
in escalation because no safe automatic outcome exists.

Optional: a facility-level scheduling tool that receives structured data
and proposes a new sequence after an ETA update or gate check-in.

## 13. Success measures

Report results over the scripted scenario set; do not claim production
outcomes from classroom data.

-   Time from first message to usable outcome.
-   Share resolved without manual takeover.
-   Conflicting or duplicate allocations.
-   Options later found infeasible.
-   No-slot escalations handled correctly.
-   Average driver waiting after rescheduling.
-   Warehouse slot utilisation.
-   Priority-policy violations.
-   Driver clarification turns.

## 14. Quality and safety requirements

-   All capacity decisions must be deterministic and testable.
-   All writes must be authenticated, validated and auditable.
-   Use idempotency for retried messages and booking commands.
-   Use transactions/atomic conditional updates for capacity commitment.
-   Do not trust an LLM-produced shipment ID, ETA or booking state
    without tool validation.
-   Treat database contents and driver text as data, not instructions.
-   Do not expose other drivers' or customers' private information.
-   Use explicit time zones and ISO-8601 timestamps; database snapshot
    timestamps use `+05:30`.
-   Make tool errors and stale data visible to the agent as structured
    outcomes.
-   Provide a human hand-off path and a safe fallback when tools fail.

## 15. MVP completion definition

The MVP is complete when all six mandatory academy deliverables are
present, the required scenarios are reproducible, the database audit is
evidenced by SQL, the agent never fabricates capacity, and a repeatable
concurrency test proves that only one competing request can successfully
commit the same slot.
