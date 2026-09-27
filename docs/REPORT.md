# SupplyChainAI: End-to-End Decision Intelligence System
## Comprehensive Technical & Operational Report

---

# Executive Summary

SupplyChainAI is a next-generation decision intelligence platform built to solve modern supply chain logistics issues. It bridges the gap between natural language interaction and rigorous mathematical optimization. Unlike pure Large Language Model (LLM) applications which hallucinate numerical answers, SupplyChainAI relies on an ensemble of highly specialized, deterministic AI agents that parse constraints, evaluate real-time risks, and compile inputs for a Google OR-Tools optimization engine. 

This report provides an in-depth breakdown of the dataset ecosystem, architectural design, multi-agent workflows, user interface, and overall system functionality.

---

# Chapter 1: Introduction & Problem Statement

## 1.1 The Challenge
Modern supply chains involve thousands of variables: global suppliers, real-time logistics delays, varying inventory levels at distribution centers (DCs), shifting consumer demand, and unpredictable weather phenomena. Human planners often rely on disjointed spreadsheets, resulting in slower reaction times and sub-optimal sourcing strategies during crises.

## 1.2 The Solution
SupplyChainAI provides a single-pane-of-glass natural language interface. Planners can ask complex queries like, "I need 10,000 units of Product A next month with the lowest risk," and the system will:
1. Deconstruct the intent.
2. Query a rich PostgreSQL database.
3. Compute the lowest cost routing and sourcing plan using Mixed-Integer Linear Programming (MILP).
4. Return an explainable, auditable recommendation.

---

# Chapter 2: Multi-Agent System Architecture

The core of SupplyChainAI is built on **LangGraph**, forming a Directed Acyclic Graph (DAG) of specialized sub-agents. 

## 2.1 The Agentic Flow
The flow follows a strict sequence to ensure data integrity:
1. **Parse Node:** Translates natural language into a structured schema (Product, Quantity, Risk Tolerance).
2. **Supervisor Node:** Decides which domain agents are required based on the intent.
3. **RAG Node:** Retrieves corporate policy documents for grounded context.
4. **Specialists:** Five domain-specific agents gather hard data.
5. **Solve Node:** Passes variables to Google OR-Tools.
6. **Validate / Replan:** Ensures the plan is feasible. If not, constraints are progressively relaxed.
7. **Explain Node:** The LLM generates a human-readable narrative.

---

# Chapter 3: Dataset Definition & Schema

SupplyChainAI operates on a robust, highly relational dataset mimicking a real-world enterprise. 

## 3.1 Catalogs and Warehouses
- **Products:** 10 SKUs, ranging from raw materials to finished goods (e.g., "Product A").
- **Distribution Centers (DCs):** 4 major hubs located strategically in Rotterdam, Chicago, Singapore, and Mumbai.

## 3.2 Supplier Network
7 distinct global suppliers are modeled with the following attributes:
- **Capacity:** Maximum monthly production output.
- **Minimum Order Quantity (MOQ):** Thresholds required for purchase.
- **Reliability History:** Statistical tracking of on-time deliveries.
- **Risk Tiers:** Tier 1 (Low Risk) through Tier 3 (High Risk).

## 3.3 Logistics Nodes
16 independent shipping lanes connect suppliers to DCs. Lanes possess:
- **Modes:** Air, Ocean, Rail.
- **Transit Times:** Estimated hours from dispatch to arrival.
- **Baseline Costs:** Fixed transport costs per unit.

## 3.4 Temporal & Environmental Data
- **Order History:** 24 months of synthetic historical orders reflecting distinct seasonal trends to fuel the demand forecasting agent.
- **Risk Events:** Live tables simulating port strikes, geopolitical tension, and weather events.
- **Fuel Indices:** Variable marine fuel multipliers that impact real-time routing costs.

---

# Chapter 4: Agent Breakdown (The "Nook and Cranny" Report)

SupplyChainAI relies on five individual specialists, ensuring separation of concerns.

## 4.1 Demand Agent
* **Purpose:** Calculates precise material requirements.
* **Mechanism:** Queries the 24-month order history. It applies a blended forecasting algorithm: combining a naive seasonal baseline with a 3-month trailing mean. 
* **Failsafe:** It separates the "user requested quantity" from the "statistical forecast," ensuring the planner sees both data points without the LLM muddying the numbers.

## 4.2 Supplier Agent
* **Purpose:** Curates an eligible roster of vendors for the optimization engine.
* **Mechanism:** Cross-references requested SKUs against vendor catalogs. It strictly filters out suppliers whose standard lead times violate the user's deadline. Rather than dropping high-risk suppliers, it passes them forward with mathematical penalty weights attached.

## 4.3 Route Agent
* **Purpose:** Computes true transportation capacity and cost.
* **Mechanism:** Iterates over the 16 shipping lanes. If a route is impacted by a live risk event (e.g., Port Congestion), it aggressively cuts the lane capacity to zero. It also calculates the *Effective Cost* by factoring in current global fuel indices.

## 4.4 Inventory Agent
* **Purpose:** Prevents unnecessary procurement spend.
* **Mechanism:** Scans all 4 DCs for current on-hand stock and reserved allocations. It calculates the exact Net Requirement needed to fulfill the demand without breaching established safety stock thresholds. 

## 4.5 Risk Agent
* **Purpose:** Quantifies vulnerability into a single, digestible metric.
* **Mechanism:** Compiles a 0–100 composite risk score. The rubric evaluates historical vendor reliability, active weather disruptions on selected lanes, and macro-market volatility. It produces an auditable matrix of "risk drivers."

---

# Chapter 5: Optimization Engine (Google OR-Tools)

The most critical rule of SupplyChainAI is: **The LLM does not do math.**

Once the five agents compile their matrices, the data is pushed to a Mixed-Integer Linear Programming (MILP) solver via Google OR-Tools.

## 5.1 Decision Variables
- `x[supplier, route]` = The integer quantity of units shipped on a given lane.

## 5.2 Mathematical Objective
The solver's goal is to minimize the total combined cost:
`Minimize: (Procurement Cost) + (Effective Transport Cost) + (Holding Cost) + (Reliability Penalty Weight)`

## 5.3 Constraints
- **Demand Satisfaction:** Total units procured plus existing inventory must equal or exceed total demand.
- **Capacity Ceilings:** No supplier or route can exceed its modeled capacity limits.
- **MOQ Floors:** If a supplier is utilized (`x > 0`), the order must exceed their minimum order quantity.

---

# Chapter 6: RAG Implementation & Knowledge Base

To prevent hallucination, the system utilizes Retrieval-Augmented Generation (RAG).

## 6.1 The Corpus
The knowledge base (`data/knowledge/`) contains markdown files dictating corporate policy regarding fuel surcharges, safety stock rules, and disruption playbooks.

## 6.2 The Vector Store
Documents are chunked and embedded into PostgreSQL using the `pgvector` extension. 

## 6.3 Hybrid Search
When a user asks a question, the Orchestrator performs a dense cosine similarity search combined with sparse lexical overlap (BM25), fused via Reciprocal Rank Fusion (RRF), pulling exact policy quotes into the explanation.

---

# Chapter 7: The "What-If" Scenario Engine

Supply chains require resiliency testing. The platform features an API route (`/api/v1/what-if`) dedicated to simulating disaster.

## 7.1 Available Scenarios
- **Demand Surge:** Spikes required inventory by an arbitrary percentage (e.g., +20%).
- **Supplier Failure:** Instantly removes a critical vendor from the solver's matrix.
- **Fuel Inflation:** Multiplies global shipping costs.
- **Route Disruption:** Closes specific logistics lanes.
- **Inventory Shortage:** Unexpectedly slashes on-hand stock.

## 7.2 Resolution
The system re-runs the entire LangGraph pipeline with the scenario patch applied, returning a side-by-side comparison of the Baseline vs. Scenario costs, delays, and risk adjustments.

---

# Chapter 8: User Interface & Frontend Workings

The UI is built on **React** and **Vite**, focusing on data density and operational clarity.

## 8.1 Dashboard Features
- **Query Input:** A centralized text area for natural language commands.
- **KPI Bar:** High-visibility metrics highlighting Total Cost, Delivery Hours, Risk Score, and Mathematical Feasibility.
- **Data Grids:** Tabular displays of the resulting Supplier Allocations (Cost, Units) and Logistics Routes (Lanes, Modes, Qty).
- **Inventory Matrix:** A per-DC breakdown of On Hand vs. Required stock.
- **Scenario Module:** A drop-down testing suite for the "What-If" engine.

## 8.2 Explainability Panel
A dedicated section that prints the LLM's natural language justification for the solver's output, alongside direct citations from the RAG evidence pool.

---

# Chapter 9: Backend & Deployment Specifications

## 9.1 API Surface (FastAPI)
- `POST /decisions`: Ingests natural language and returns the optimized graph state.
- `POST /what-if`: Re-runs a specific graph trace with manipulated variables.
- `GET /catalog`: Surfaces available products and suppliers.

## 9.2 Containerization
The entire application is dockerized. A single `docker compose up` command launches the PostgreSQL/pgvector instance, the Python FastAPI server, and the Node/React frontend simultaneously.

---

# Chapter 10: Conclusion

SupplyChainAI represents a paradigm shift in how operations teams interact with enterprise data. By delegating data-gathering to specialized LLM agents and mathematical optimization to deterministic solvers, it eliminates AI hallucination while maintaining the ease of conversational interfaces. The comprehensive dataset, intricate agent logic, and robust UI combine to create a highly effective, end-to-end decision intelligence platform.
