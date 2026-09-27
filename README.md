# SupplyChainAI - Comprehensive End-to-End Project Report

**SupplyChainAI** is an advanced multi-agent decision intelligence platform for supply-chain planning. It allows users to ask supply chain questions in plain English and returns an explainable, cost-optimized plan backed by real mathematical optimization (Google OR-Tools) rather than LLM guesswork.

This document serves as the comprehensive report detailing the dataset architecture, the intricate workings of all sub-agents, the optimization engine, and the front-end user interface.

---

## 1. Complete Dataset Report

The project is built on a rich, relational database hosted in PostgreSQL. It is designed to mimic a complex, real-world supply chain ecosystem. 

### Core Entities & Data Points:
- **Products Catalog:** Contains 10 unique product SKUs (including the primary test product, "Product A").
- **Suppliers:** 7 global suppliers, each distinctly modeled with historical reliability scores, risk tiers, and capacity constraints.
- **Distribution Centers (DCs):** 4 major global warehouses located in Rotterdam, Chicago, Singapore, and Mumbai.
- **Logistics Network (Routes):** 16 distinct shipping routes (lanes) connecting suppliers to warehouses. Each lane has specific transportation modes (Ocean, Air, Rail), baseline costs, and capacities.
- **Historical Data:** 24 months of synthetic seasonal order history to train and test the Demand forecasting agent.
- **Live Event Simulation:** Built-in tables for active risk events (e.g., port strikes), real-time weather anomalies, and fluctuating marine fuel indices.
- **Knowledge Base (RAG):** A markdown corpus of corporate policies, disruption playbooks, and safety stock guidelines vectorized using `pgvector` for context retrieval.

---

## 2. The Multi-Agent Ecosystem (Nook & Cranny Report)

The brain of SupplyChainAI operates via **LangGraph**, orchestrating five highly specialized AI agents that act as fact-gatherers and constraint builders. 

### A. The Orchestrator (Supervisor & RAG)
Before specialists are invoked, the system parses the user's natural language intent (e.g., *"I need 10k units of Product A with low risk"*). It then uses **Hybrid RAG** (dense vector search + sparse keyword search) to retrieve relevant company policies to ground the agents in corporate reality.

### B. Demand Agent
* **Role:** Determines exactly *how much* product is required.
* **Inner Workings:** Analyzes the past 24 months of order data. If historical data exceeds 12 months, it blends a seasonal naive forecast with a 3-month trailing mean. It separates the "user requested quantity" from the "statistically forecasted quantity" to ensure planners have full visibility.

### C. Supplier Agent
* **Role:** Evaluates supplier viability and eligibility.
* **Inner Workings:** Cross-references the requested product against the 7 available suppliers. It filters out suppliers whose lead times exceed the user's requested horizon or who are explicitly failing in "what-if" simulations. High-risk suppliers are flagged and penalized mathematically, rather than arbitrarily removed.

### D. Route Agent
* **Role:** Maps logistics and calculates true transportation costs.
* **Inner Workings:** Analyzes the 16 shipping lanes. If a route is disrupted (e.g., due to a simulated weather event or port strike), it zeroes out the capacity (`capacity_units = 0`). It also calculates the *effective cost* by multiplying the baseline shipping rate by the current marine fuel index.

### E. Inventory Agent
* **Role:** Prevents over-purchasing by analyzing current stock.
* **Inner Workings:** Reviews inventory across the 4 DCs. Calculates `Available = On Hand - Reserved`. It determines the exact net procurement requirement by deducting available stock from the demand, while strictly ensuring that safety-stock thresholds are never breached.

### F. Risk Agent
* **Role:** Quantifies supply chain vulnerability.
* **Inner Workings:** Compiles a 0–100 composite risk score. It evaluates supplier reliability history, active weather disruptions, route closures, and macro-market fuel indices to generate a human-readable risk narrative alongside the final cost.

### The Optimization Engine (Google OR-Tools)
*Crucially, the LLM does not invent the final numbers.* The variables collected by the 5 agents are passed to a Mixed-Integer Linear Programming (MILP) solver. The solver mathematically minimizes total cost (procurement + transport + holding) while adhering to the risk and capacity constraints, outputting the absolute optimal allocation.

---

## 3. User Interface (UI) Report

The front-end is built with **React** and **Vite**, designed to be a sleek, responsive, and data-dense dashboard for supply chain planners. 

### Key Interface Modules:
1. **Natural Language Input:** A text area where users can type complex planning requests in plain English.
2. **KPI Dashboard:** Top-level metrics displaying:
   - Statistically Forecasted Units
   - Total Optimized Cost ($)
   - Delivery Time (Hours)
   - Composite Risk Score
   - Mathematical Solver Status (e.g., Optimal, Feasible)
3. **Allocation & Route Tables:** Granular data tables showing exactly *which* supplier to buy from, *how many* units to purchase, and *which* transport lane to use.
4. **Inventory Plan Table:** A DC-by-DC breakdown of On Hand, Reserved, Available, and Safety Stock levels.
5. **"What-If" Scenario Engine:** A dedicated module allowing users to stress-test the AI's plan. Users can select scenarios like:
   - *Supplier Failure*
   - *Demand Spikes (e.g., +20%)*
   - *Fuel Price Hikes*
   - *Route Disruptions*
   The UI will re-run the entire agent pipeline and generate a side-by-side comparative table showing Baseline vs. Scenario deltas.
6. **Explainability Engine:** A dedicated text pane where the LLM explains *why* the mathematical solver made its choices, citing the specific company policy documents retrieved via RAG.

---

## 4. Deployment & Infrastructure

The project is fully containerized and production-ready:
- **Backend:** FastAPI (Python), LangGraph, Google OR-Tools.
- **Database:** PostgreSQL 16 with `pgvector` (via Docker Compose).
- **Frontend:** React + Vite.

### How to Run Locally:
Ensure Docker Desktop is running, then execute the following in the main project directory:
```bash
docker compose up --build
```
- **Frontend UI:** `http://localhost:5173`
- **Backend API:** `http://localhost:8000/docs`

---
*End of Report.*
