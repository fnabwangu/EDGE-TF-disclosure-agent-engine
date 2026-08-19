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

## Live ChatGPT MCP Testing

EDGE's remote MCP service is `api.app:app`. It binds to all interfaces and uses
`PORT` (default `8600`). The MCP endpoint is `/mcp`; the unauthenticated health
endpoint is `/health`.

### GitHub Codespaces

From the repository root, set a bearer token in the shell and start the service:

```bash
export EDGE_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export PORT=8600
python -m uvicorn api.app:app --host 0.0.0.0 --port "$PORT"
```

In the Codespaces **Ports** panel, make port `8600` public. The MCP URL is:

```text
https://<codespace-name>-8600.app.github.dev/mcp
```

Use the exact forwarded URL shown by the Ports panel if your Codespaces domain
differs. Verify the service before registering it with ChatGPT:

```bash
curl "https://<codespace-name>-8600.app.github.dev/health"
curl -H "Authorization: Bearer $EDGE_API_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  "https://<codespace-name>-8600.app.github.dev/mcp"
```

The discovered tools include `edge_create_project`, `edge_get_project_state`,
`edge_record_ui_event`, `edge_component_action`, and `edge_get_view`. Approval,
execution, order submission, broker credentials, and kill-switch reset tools are
not exposed.

### Docker Compose

Copy `.env.template` to `.env`, replace `EDGE_API_TOKEN` with a generated value,
then run `docker compose up mcp`. Compose exposes the MCP service on `PORT` and
the console separately on port `8501`.

### Production

Deploy the MCP service as a long-running web process behind a managed HTTPS
proxy or platform domain. Set `PORT`, `EDGE_API_TOKEN`, and any provider secrets
in the platform secret manager. Register only the stable HTTPS `/mcp` URL in
ChatGPT Developer Mode; never place secrets in the widget or the MCP URL.
========================================================================================
