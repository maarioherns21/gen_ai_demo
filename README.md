# Agentic Vacation Planner

An **AI-driven multi-agent architecture** designed to plan, budget, and orchestrate vacations intelligently.  
This repository includes both the **Next.js frontend** and the **FastAPI backend**.

---

## Project Architecture

```bash

agentic-vacation-planner/
│
├── README.md
├── .env
├── .gitignore
├── docker-compose.yml
├── package.json
├── requirements.txt
├── Makefile
│
├── frontend/                     # Next.js Web App (User Interface)
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── itinerary/[id]/page.tsx
│   ├── components/
│   │   ├── ChatWidget.tsx
│   │   ├── ItineraryCard.tsx
│   │   ├── BudgetChart.tsx
│   │   └── PreferenceForm.tsx
│   ├── lib/
│   │   └── api.ts                # Axios/Fetch client for Orchestrator API
│   ├── public/
│   │   └── icons/
│   ├── styles/
│   │   └── globals.css
│   └── next.config.js
│
├── backend/                      # FastAPI or Node API Gateway (BFF)
│   ├── main.py                   # API entry (FastAPI)
│   ├── routers/
│   │   ├── trips.py              # /v1/trips endpoints
│   │   ├── profile.py            # /v1/profile endpoints
│   │   ├── booking.py            # booking cart + confirmation
│   │   └── monitor.py            # alerts, subscriptions
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── controller.py         # task graph + orchestration logic
│   │   ├── state_manager.py
│   │   └── evaluator.py
│   ├── agents/
│   │   ├── base_agent.py         # common agent superclass
│   │   ├── planner_agent.py
│   │   ├── transport_agent.py
│   │   ├── lodging_agent.py
│   │   ├── activity_agent.py
│   │   ├── budget_agent.py
│   │   ├── critic_agent.py
│   │   ├── compliance_agent.py
│   │   ├── booking_agent.py
│   │   ├── calendar_agent.py
│   │   └── notifier_agent.py
│   ├── tools/
│   │   ├── flights_api.py
│   │   ├── hotels_api.py
│   │   ├── events_api.py
│   │   ├── weather_api.py
│   │   ├── visa_checker.py
│   │   ├── forex_api.py
│   │   └── safety_api.py
│   ├── db/
│   │   ├── models.py             # SQLAlchemy models (trip, itinerary_day, line_item)
│   │   ├── database.py           # session setup
│   │   └── vector_store.py       # pgvector / FAISS integration
│   ├── schemas/
│   │   ├── trip_schema.py
│   │   ├── profile_schema.py
│   │   └── tool_schema.py
│   ├── config/
│   │   ├── settings.py
│   │   ├── secrets.toml
│   │   └── logging.yaml
│   ├── tests/
│   │   ├── test_agents/
│   │   ├── test_endpoints/
│   │   ├── test_orchestration.py
│   │   └── data/
│   └── utils/
│       ├── logger.py
│       ├── cache.py
│       ├── retry.py
│       └── validation.py
│
├── data/                         # Cached results, sample data, embeddings
│   ├── embeddings/
│   ├── sample_trips/
│   └── cache.db
│
├── infra/                        # IaC, deployment, and CI/CD
│   ├── Dockerfile.api
│   ├── Dockerfile.web
│   ├── k8s/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── ingress.yaml
│   ├── terraform/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── ci-cd/
│       └── github-actions.yaml
│
└── docs/                         # Design and documentation
    ├── architecture-diagram.png
    ├── agent-contracts/
    ├── api-spec.yaml
    ├── prompt-templates/
    │   ├── planner_agent.md
    │   ├── critic_agent.md
    │   └── budget_agent.md
    └── roadmap.md


```

## Backend Setup (FastAPI)

This guide uses **[uv](https://github.com/astral-sh/uv)** for environment creation and dependency management.  
`uv` is a modern Python package manager that automatically handles virtual environments and dependency locking.

###  1. Install UV
```bash
brew install uv
uv --version
```
###  2. Initialize Environment
```bash
uv init .
```
This will:
* Create a .venv virtual environment
* Generate a uv.lock file
* Install all dependencies listed in requirements.txt

###  3.  Sync Dependencies
```bash
uv sync
```
This installs all required packages and ensures reproducible builds.

###  4. Activate Virtual Environment (e.g.,)
```bash
source .venv/bin/activate
```
To verify:
```bash
which python
```
# should show path ending with `.venv/bin/python`

###  5. Run the FastAPI Server
```bash
uv run uvicorn backend.main:app --reload
```
This will:
* Launch the backend on http://127.0.0.1:8000
* Auto-reload on file changes
Access Swagger UI at: http://127.0.0.1:8000/docs