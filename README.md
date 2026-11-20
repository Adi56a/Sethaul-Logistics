# SetuHaul Logistics — Autonomous Exception Resolution & Dock Scheduling

**Project:** FDE Academy Mini Project 2  
**Domain:** Conversational Full-Truckload Freight Exception Management & Dock Rescheduling  
**System Snapshot:** 4 August 2026, Asia/Kolkata (`+05:30`)

---

## 1. Project Overview

SetuHaul Logistics coordinates freight movements across North and West India. When trucks encounter in-transit disruptions (highway traffic, mechanical breakdowns, loading backlogs), they communicate delays in natural language.

This system provides a **safe, context-aware conversational agent** that:
1. Accurately extracts delay and constraint declarations from colloquial driver messages.
2. Identifies driver identity and resolves multi-shipment ambiguities safely.
3. Evaluates dock availability using a pure deterministic feasibility engine (handling weight, dock type, operating hours, and breakdowns).
4. Enforces zero double-booking guarantees using atomic SQLite transactions and database-level partial unique indexes.
5. Escalates unresolvable capacity exceptions to warehouse human operators with a complete audit record.

---

## 2. Core Architectural Philosophy

```
  Driver Chat UI (Streamlit / Mobile Web)
        │
        ▼
  LangChain Conversational Agent  (Coordinates: extracts intent, clarifies, explains)
        │
        ▼
  Deterministic Logistics Engine  (Decides: compatibility, feasibility, priority)
        │
        ▼
  SQLite System of Record (Snapshot) (Guarantees: BEGIN IMMEDIATE, partial unique indexes)
```

- **LLM Coordinates, Deterministic Code Commits:** The LLM NEVER writes SQL or invents capacity.
- **Read-Only Option Queries:** Displaying feasible slots is ephemeral and creates zero database capacity holds.
- **Concurrency Protection:** SQLite `BEGIN IMMEDIATE` transactions backed by `ux_active_appointment_per_slot`.
- **Unified Model Access:** Single OpenRouter AI API key (`OPENROUTER_API_KEY`) connecting to modern instruction-tuned models with fallback support.

---

## 3. Technology Stack & Verified Library Versions

- **Python Runtime:** Python 3.12.3
- **Database:** SQLite 3.x with standard library `sqlite3`
- **Agent Framework:** `langchain==1.5.2`, `langchain-core==1.8.3`, `langchain-openai==1.8.3`
- **API & LLM Client:** `openai==3.55.1` (configured for OpenRouter endpoint), `fastapi==0.165.0`, `uvicorn==0.54.0`
- **Data Validation:** `pydantic==2.13.4`
- **User Interface:** `streamlit==1.36.0`

---

## 4. Repository Structure

```text
Mini-Project-2/
├── README.md                          # Project documentation and quickstart
├── .env.example                       # Environment template (OpenRouter configured)
├── setuhaul_freight_operations.db     # Authoritative SQLite operational snapshot
├── setuhaul_schema_and_seed.sql       # Reproducible schema and seed data
├── setuhaul_database_guide.md         # Schema and scenario guide
├── setuhaul_data_dictionary.csv       # 18-table column catalog
├── docs/                              # Formal Academy Deliverables
│   ├── PRD.md                         # Product Requirements Document
│   ├── ARCHITECTURE_TECH_STACK.md     # Architecture & technical specifications
│   ├── PHASES.md                      # Implementation plan and exit criteria
│   ├── PROGRESS.md                    # Living phase completion tracker
│   ├── source-audit.md                # Phase 0 source inventory & SHA-256 hashes
│   ├── problem-definition.md          # Deliverable 1: Problem framing & boundaries
│   ├── data-audit.md                  # Deliverable 1: Query-verified data audit
│   ├── decision-register.md           # Deliverable 2: Answers to 7 student questions (ADRs)
│   ├── domain-model.md                # Relational entities, invariants, error taxonomy
│   ├── state-machine.md               # State machines and Mermaid sequence flows
│   └── client-readout.md              # Deliverable 6: Plain-language executive readout
├── app/                               # Application Core
│   ├── health_check.py                # System and database verification tool
│   ├── agent/                         # LangChain agent, prompt templates, tool wrappers
│   ├── tools/                         # Typed tool schemas for agent
│   ├── services/                      # Deterministic feasibility & booking services
│   ├── repositories/                  # SQLite transactional data access
│   ├── api/                           # FastAPI REST service boundary
│   └── ui/                            # Streamlit driver chat and operations portal
├── database/                          # Database migrations & queries
├── sql/audit/                         # Reproducible audit SQL queries (Phase 1)
├── tests/                             # Unit, integration, and concurrency test suites
│   ├── unit/                          # Feasibility & Agent unit tests
│   ├── integration/                   # Booking & API integration tests
│   ├── concurrency/                   # Deliverable 5: Multi-threaded race condition tests
│   └── scenarios/                     # Multi-turn conversation tests
└── eval/                              # Scenario evaluation and benchmarks
    ├── scenarios/eval_runner.py       # Deliverable 4: 22-scenario evaluation harness
    └── results.md                     # Formal evaluation benchmark report
```

---

## 5. Quickstart & Execution Guide

### 5.1 Environment Setup
```bash
# Copy environment configuration
cp .env.example .env

# Edit .env and paste your OpenRouter API key:
# OPENROUTER_API_KEY=your_key_here
```

### 5.2 System Health Check
Verify database connection, schema objects, foreign keys, and indexes:
```bash
python app/health_check.py
```

### 5.3 Launch Interactive UI (Driver Portal & Operations Review)
```bash
streamlit run app/ui/app.py
```
- **Driver Chat Portal:** Report delays in natural language, view feasible slots, book appointments.
- **Operations Review Queue:** Inspect and resolve human escalations (e.g. reefer breakdowns, dual-shipment ambiguities).

### 5.4 Launch REST API Service
```bash
uvicorn app.api.main:app --reload --port 8000
```
API Documentation available at: `http://localhost:8000/docs`

---

## 6. Running Tests & Scenario Evaluations

### Run All 30 Automated Tests
Executes unit, integration, concurrency, and conversational scenario tests:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

### Run Multi-Threaded Concurrency Integrity Test (Deliverable 5)
Proves that two simultaneous requests targeting the same slot safely resolve to 1 winner and 1 conflict with zero double-booking:
```bash
python -m unittest tests/concurrency/test_competing_requests.py
```

### Run 22-Scenario Academy Evaluation Suite (Deliverable 4)
Executes all 22 seeded operational scenarios with millisecond latency benchmarking:
```bash
python eval/scenarios/eval_runner.py
```

---

## 7. Mandatory Academy Deliverables Mapping

| Deliverable ID | Requirement | Repository Artifact Link |
|---|---|---|
| **Deliverable 1** | Problem Definition Sheet + Data Audit | [`docs/problem-definition.md`](file:///d:/FDE-Acdemy/Mini-Project-2/docs/problem-definition.md) & [`docs/data-audit.md`](file:///d:/FDE-Acdemy/Mini-Project-2/docs/data-audit.md) |
| **Deliverable 2** | Decision Register (7 Academy ADRs) | [`docs/decision-register.md`](file:///d:/FDE-Acdemy/Mini-Project-2/docs/decision-register.md) |
| **Deliverable 3** | Working Prototype (Codebase & UI) | [`app/agent/`](file:///d:/FDE-Acdemy/Mini-Project-2/app/agent/), [`app/services/`](file:///d:/FDE-Acdemy/Mini-Project-2/app/services/), [`app/api/`](file:///d:/FDE-Acdemy/Mini-Project-2/app/api/), [`app/ui/app.py`](file:///d:/FDE-Acdemy/Mini-Project-2/app/ui/app.py) |
| **Deliverable 4** | Scenario Run (22 Scenarios Tested) | [`eval/scenarios/eval_runner.py`](file:///d:/FDE-Acdemy/Mini-Project-2/eval/scenarios/eval_runner.py) & [`eval/results.md`](file:///d:/FDE-Acdemy/Mini-Project-2/eval/results.md) |
| **Deliverable 5** | Concurrency & Integrity Proof | [`tests/concurrency/test_competing_requests.py`](file:///d:/FDE-Acdemy/Mini-Project-2/tests/concurrency/test_competing_requests.py) & [`tests/concurrency/concurrency_test_report.md`](file:///d:/FDE-Acdemy/Mini-Project-2/tests/concurrency/concurrency_test_report.md) |
| **Deliverable 6** | Executive Client Readout | [`docs/client-readout.md`](file:///d:/FDE-Acdemy/Mini-Project-2/docs/client-readout.md) |
#   S e t h a u l - L o g i s t i c s  
 