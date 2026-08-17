# EDGE-TF Disclosure Agent Engine

This repository is a scaffold for the EDGE-TF disclosure agent engine. It provides a minimal, well-organized project structure with placeholder implementations for each component so you can iterate quickly.

See console/ for the Streamlit operator UI and src/ for the core agent modules. Run tests with pytest.

========================================================================================
MODULE: Repository Root Documentation (README.md)
PURPOSE: Provide a comprehensive technical overview of the Edge-TF / Reverse 
         Engineering Alpha production execution engine, architecture, pipeline 
         runtime, directory topology, and operational guidelines.
========================================================================================

CONTENT SECTIONS:
    1. System Overview & Core Philosophy
       - Deconstructs ETF disclosures as an observable intelligence layer of capital allocation[cite: 1, 2].
       - Strategy-First vs Ticker-First paradigm[cite: 1, 2].
    2. Architecture & Pipeline Topology
       - 8-Layer event-driven pipeline breakdown[cite: 1, 3].
       - Data contracts and point-in-time inequality enforcement (DecisionTime >= InfoAvailableTime)[cite: 1].
    3. Quantitative & Falsification Engine
       - Active Quantity Deviation (AQD) formula and unit share normalization (u = q / N)[cite: 1].
       - Institutional Adoption Velocity (IAV) 6-factor composite vector and penalty matrix[cite: 1].
       - Manager cluster de-duplication (ManagerHHI) and half-life decay (δ^τ)[cite: 1].
    4. Trade Design & Risk Governance
       - Multi-factor Implementation Fit Score (TradeFit = S * E * L * D * R)[cite: 1].
       - Secondary constrained convex optimization formulation[cite: 1].
       - Deterministic safety gates and NO_TRADE_PERMISSIBLE state rule[cite: 1].
    5. Repository Directory Layout & Module Index
    6. Local Setup, Testing, and Deployment via Docker Compose
========================================================================================
