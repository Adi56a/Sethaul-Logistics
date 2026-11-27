# SetuHaul Logistics — Autonomous Exception Resolution & Dock Scheduling

**Project:** FDE Academy Mini Project 2  
**Domain:** Conversational Full-Truckload Freight Exception Management & Dock Rescheduling  
**System Snapshot:** 4 August 2026, Asia/Kolkata (`+05:30`)

---

## 1. Project Overview

SetuHaul Logistics coordinates freight movements across North and West India. When trucks encounter in-transit disruptions (highway traffic, mechanical breakdowns, loading backlogs), they communicate delays in natural language.

This system provides a **safe, context-aware conversational agent and operational platform** that:
1. Accurately extracts delay and constraint declarations from colloquial driver messages.
2. Identifies driver identity and resolves multi-shipment ambiguities safely.
3. Evaluates dock availability using a pure deterministic feasibility engine (handling weight, dock type, operating hours, and breakdowns).
4. Enforces zero double-booking guarantees using atomic SQLite transactions and database-level partial unique indexes.
5. Escalates unresolvable capacity exceptions to warehouse human operators with a complete audit record.
6. Delivers an enterprise **Observability, Distributed Tracing, Error Monitoring, and Automated Evaluation** dashboard.
7. Features a cleanly segregated architecture: **Vercel-ready Frontend** and **Containerized/Cloud-ready Backend**.

---

## 2. Core Architectural Philosophy

```
  Driver Chat & Ops UI (React 19 + Vite SPA) [Deployed on Vercel]
                      │
                      ▼ HTTP/JSON (REST APIs)
  FastAPI Service Boundary & Request Tracing Middleware [Deployed on Cloud/Docker]
                      │
                      ▼ OpenTelemetry-Compatible Tracer & Metrics Aggregator
  LangChain Conversational Agent  (Coordinates: extracts intent, clarifies, explains)
                      │
                      ▼ Real Background Tool Invocation (Nested Spans)
  Deterministic Logistics Engine  (Decides: compatibility, feasibility, priority)
                      │
                      ▼ Transactional Commit & Error Logging
  SQLite System of Record (Snapshot) (Guarantees: BEGIN IMMEDIATE, partial unique indexes)
```

- **LLM Coordinates, Deterministic Code Commits:** The LLM NEVER writes SQL or invents capacity.
- **Read-Only Option Queries:** Displaying feasible slots is ephemeral and creates zero database capacity holds.
- **Concurrency Protection:** SQLite `BEGIN IMMEDIATE` transactions backed by `ux_active_appointment_per_slot`.
- **Unified Model Access:** Single OpenRouter AI API key (`OPENROUTER_API_KEY`) connecting to modern instruction-tuned models (`deepseek/deepseek-chat`).
- **Full Observability:** Automatic distributed tracing with waterfall Gantt charts, live P50/P95/P99 latency percentiles, centralized error monitoring, and 1-click automated evaluation suites.

---

## 3. Technology Stack & Verified Library Versions

### Backend (`/backend`)
- **Python Runtime:** Python 3.11+ / 3.12
- **Database:** SQLite 3.x with standard library `sqlite3` (foreign keys, atomic transactions)
- **API Framework:** `fastapi>=0.115.0`, `uvicorn[standard]>=0.30.0`
- **Agent Framework:** `langchain-core>=0.2.0`, `langchain-openai>=0.1.0`
- **Model Provider:** OpenRouter API (`deepseek/deepseek-chat`)
- **Data Validation:** `pydantic>=2.8.0`
- **Observability:** Custom in-process OpenTelemetry-compatible tracing, thread-safe metrics collector, error monitor, SQLite telemetry store

### Frontend (`/frontend`)
- **Framework:** `react@19.0.0`, `react-dom@19.0.0`
- **Build Tool:** `vite@6.2.0`
- **Icons:** `lucide-react@1.16.0`
- **Deployment:** Vercel SPA (configured with `vercel.json` rewrites and `VITE_API_URL` environment variable)

---

## 4. Repository Segregation & Structure

The repository is cleanly partitioned into independent `backend/` and `frontend/` roots for isolated CI/CD and deployment:

```text
Mini-Project-2/
├── README.md                          # Master project documentation
├── PHASES.md                          # Phase tracker and delivery milestones
├── ARCHITECTURE_TECH_STACK.md         # Architecture and technical specifications
├── PRD.md                             # Product Requirements Document
├── .gitignore                         # Root Git ignore rules
│
├── backend/                           # STANDALONE BACKEND (Docker / Cloud Deployable)
│   ├── app/                           # Backend Application Core
│   │   ├── agent/                     # LangChain agent, prompt templates, tool wrappers
│   │   ├── api/                       # FastAPI REST endpoints & tracing middleware
│   │   ├── observability/             # Tracing, Metrics, Error Monitoring & Eval Engine
│   │   ├── repositories/              # Parameterized SQLite data access
│   │   ├── services/                  # Deterministic feasibility & booking engines
│   │   ├── tools/                     # Typed tool schemas for agent
│   │   └── health_check.py            # System health and schema validator
│   ├── tests/                         # Automated Test Suites (36 tests)
│   │   ├── unit/                      # Feasibility & Agent unit tests
│   │   ├── integration/               # Booking & API integration tests
│   │   ├── concurrency/               # Deliverable 5: Multi-threaded race condition tests
│   │   └── scenarios/                 # Multi-turn conversational scenario tests
│   ├── eval/                          # Scenario Evaluations (22 Scenarios)
│   │   ├── scenarios/eval_runner.py   # Authoritative 22-scenario evaluation harness
│   │   └── results.md                 # Formal benchmark report (100% pass, 2.04 ms avg)
│   ├── setuhaul_freight_operations.db # Authoritative SQLite operational snapshot
│   ├── setuhaul_schema_and_seed.sql   # Reproducible schema and seed data
│   ├── requirements.txt               # Pinned Python dependencies
│   ├── Dockerfile                     # Multi-stage container definition
│   ├── run.py                         # Simple CLI entrypoint
│   └── .env.example                   # Backend environment template
│
├── frontend/                          # STANDALONE FRONTEND (Vercel Deployable)
│   ├── src/
│   │   ├── App.jsx                    # 4-Tab Dashboard: Chat, Ops Review, Facilities, Observability
│   │   ├── main.jsx                   # React root entrypoint
│   │   └── index.css                  # Responsive design system & waterfall styling
│   ├── index.html                     # HTML root template
│   ├── vite.config.js                 # Dev server proxy configuration
│   ├── vercel.json                    # Vercel SPA routing rewrite rules
│   ├── package.json                   # Dependencies and build scripts
│   └── .env.example                   # Frontend environment template (VITE_API_URL)
│
└── docs/                              # Formal Academy Deliverables & Engineering ADRs
    ├── problem-definition.md          # Deliverable 1: Problem framing & boundaries
    ├── data-audit.md                  # Deliverable 1: Query-verified data audit
    ├── decision-register.md           # Deliverable 2: Answers to 7 student questions (ADRs)
    ├── domain-model.md                # Relational entities, invariants, error taxonomy
    ├── state-machine.md               # State machines and Mermaid sequence flows
    ├── source-audit.md                # Phase 0 source inventory & SHA-256 hashes
    └── client-readout.md              # Deliverable 6: Plain-language executive readout
```

---

## 5. Observability, Tracing, Error Monitoring & Evals

The system includes an integrated observability platform accessible under the **"📈 Observability & Evals"** tab:

1. **Telemetry & Live Metrics:**
   - Real-time P50, P95, and P99 latency percentiles.
   - Total requests, success rate %, error rate %, and server uptime.
   - Per-tool execution breakdown table (calls, successes, failures, success rate, average latency).

2. **Distributed Tracing & Waterfall Gantt Visualization:**
   - OpenTelemetry-compatible context propagation assigning unique `trace_id` headers.
   - Nested spans (`http`, `agent`, `tool`, `db`, `internal`).
   - Interactive waterfall timeline explorer showing start offsets, span durations, and input/output attributes.

3. **Error Monitoring & Audit:**
   - Automatic exception interception capturing stack traces, taxonomy, severity (`CRITICAL`, `ERROR`, `WARNING`), and originating `trace_id`.
   - Supervisor error resolution log with 1-click resolution actions.

4. **Automated 22-Scenario Evaluation Suite:**
   - Interactive 1-click button: **"▶ Run 22-Scenario Suite"**.
   - Directly executes the authoritative validators against all 22 operational scenarios.
   - Displays real-time pass/fail badges, category tags, latency benchmarks, and scenario assertion details.

---

## 6. Local Quickstart Guide

### 6.1 Backend Setup & Execution

```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment (optional but recommended)
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # Linux / macOS

# Install dependencies
pip install -r requirements.txt

# Configure OpenRouter API key
cp .env.example .env
# Edit .env and set: OPENROUTER_API_KEY=your_openrouter_key_here

# Run backend server
python run.py
# Or directly via uvicorn:
# uvicorn app.api.main:app --reload --port 8000
```
- Backend API will run on **`http://localhost:8000`**.
- OpenAPI / Swagger documentation: **`http://localhost:8000/docs`**.
- Health check endpoint: **`http://localhost:8000/health`**.

### 6.2 Frontend Setup & Execution

```bash
# Open a new terminal and navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Run Vite development server
npm run dev
```
- Frontend will run on **`http://localhost:5173`**.
- The Vite development server automatically proxies `/api` and `/health` requests to `http://localhost:8000`.

---

## 7. Cloud Deployment Guide

### 7.1 Frontend Deployment on Vercel

The frontend is fully configured for zero-config Vercel deployment:
1. **Repository Setup:** Push the repository to GitHub/GitLab.
2. **New Project in Vercel:** Click **Add New Project** and select this repository.
3. **Build & Development Settings:**
   - **Root Directory:** `frontend`
   - **Framework Preset:** `Vite`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
4. **Environment Variables:**
   - Add `VITE_API_URL`: The public URL of your deployed backend (e.g., `https://setuhaul-backend.railway.app`).
5. **Deploy:** Click **Deploy**. Vercel will build the frontend and serve it globally with SPA route rewrites configured via `frontend/vercel.json`.

### 7.2 Backend Deployment (Render, Railway, AWS, Docker)

The backend is completely containerized via `backend/Dockerfile`:
```bash
# Build the Docker image
cd backend
docker build -t setuhaul-backend .

# Run the container
docker run -p 8000:8000 -e OPENROUTER_API_KEY="your_key" setuhaul-backend
```

**Deploying to Render / Railway:**
1. Set Root Directory to `backend`.
2. Select **Docker** or **Python** environment.
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn app.api.main:app --host 0.0.0.0 --port 8000`
5. Set Environment Variable: `OPENROUTER_API_KEY=your_key`.

---

## 8. Automated Testing & Verification

All test suites can be executed inside `backend/`:

### 8.1 Run All 36 Unit, Integration & Concurrency Tests
```bash
cd backend
python -m unittest discover -s tests -p "test_*.py"
```
*Expected Result: `Ran 36 tests ... OK`*

### 8.2 Run Concurrency Race Condition Suite (Deliverable 5)
```bash
cd backend
python -m unittest tests/concurrency/test_competing_requests.py
```
*Expected Result: Proves 1 winner confirmed, 1 conflict prevented, zero double-booking.*

### 8.3 Run 22-Scenario Evaluation Suite (Deliverable 4)
```bash
cd backend
python eval/scenarios/eval_runner.py
```
*Expected Result: `Passed: 22 / 22, Success Rate: 100.0%, Average Latency: ~2 ms`*

### 8.4 Verify Production Frontend Build
```bash
cd frontend
npm run build
```
*Expected Result: Vite transforms modules and generates `dist/index.html` cleanly.*

---

## 9. Academy Deliverables Matrix

| Deliverable ID | Requirement | Repository Artifact Link |
|---|---|---|
| **Deliverable 1** | Problem Definition Sheet + Data Audit | [`docs/problem-definition.md`](file:///d:/FDE-Acdemy/Mini-Project-2/docs/problem-definition.md) & [`docs/data-audit.md`](file:///d:/FDE-Acdemy/Mini-Project-2/docs/data-audit.md) |
| **Deliverable 2** | Decision Register (7 Academy ADRs) | [`docs/decision-register.md`](file:///d:/FDE-Acdemy/Mini-Project-2/docs/decision-register.md) |
| **Deliverable 3** | Working Prototype (Codebase & UI) | [`backend/app/`](file:///d:/FDE-Acdemy/Mini-Project-2/backend/app/) & [`frontend/src/`](file:///d:/FDE-Acdemy/Mini-Project-2/frontend/src/) |
| **Deliverable 4** | Scenario Run (22 Scenarios Tested) | [`backend/eval/scenarios/eval_runner.py`](file:///d:/FDE-Acdemy/Mini-Project-2/backend/eval/scenarios/eval_runner.py) & [`backend/eval/results.md`](file:///d:/FDE-Acdemy/Mini-Project-2/backend/eval/results.md) |
| **Deliverable 5** | Concurrency Test Suite | [`backend/tests/concurrency/test_competing_requests.py`](file:///d:/FDE-Acdemy/Mini-Project-2/backend/tests/concurrency/test_competing_requests.py) |
| **Deliverable 6** | Executive Readout & Client Handover | [`docs/client-readout.md`](file:///d:/FDE-Acdemy/Mini-Project-2/docs/client-readout.md) |
