# Edge-TF™ Configuration & Policy Manual
**Architecture Specification & Operational Governance Guide**

---

## 1. Executive Summary & Purpose

This directory acts as the immutable **Single Source of Truth (Binder specification)** for the Edge-TF agentic trading engine. It defines:
1. The investable multi-asset ETF universe.
2. The Strategy-First hierarchical business function taxonomy.
3. Hard mathematical risk boundaries and deterministic gating policies.
4. Quantitative model hyperparameters and structural penalty matrices.

Every downstream calculation in `src/quant_engine/`, reasoning prompt in `src/inference/`, and execution order in `src/execution/` is strictly parameterized by the JSON declarations contained in this directory[cite: 1, 2].

---

## 2. Fund Universe Curation & Operational SOP

### 2.1 The 5 Inclusion Criteria
Before any ETF is appended to `fund_universe.json`, it must pass five mandatory screening hurdles:

1. **Daily Disclosure Transparency (SEC Rule 6c-11)**: The fund must publish unmasked daily portfolio holdings (representing prior business day close NAV inventory). Semi-transparent, proxy basket, or delayed 13F structures are strictly prohibited.
2. **Manager Cluster Resolution**: The fund's parent adviser, subadviser, and research team must be mapped to a canonical `manager_cluster_id` to eliminate artificial breadth inflation.
3. **Strategic Purity Floor ($S \ge 0.70$)**: The fund’s mandate must explicitly target one or more business functions defined in `strategy_ontology.json`.
4. **Execution Liquidity & Tradability**: The wrapper must maintain institutional-quality bid-ask spreads, primary creation unit liquidity, and low premium/discount volatility.
5. **Point-in-Time Causality**: Disclosures must provide auditable timestamps ensuring $\text{DecisionTime} \ge \text{InformationAvailableTime}$.

### 2.2 Fund Role Classifications
Each fund is assigned one of six operational classes:
* `active_thematic`: Discretionary thematic portfolios providing early initiation and accumulation signals.
* `rules_based_thematic`: Systematic thematic index trackers used to map baseline universe definitions and scheduled rebalance events.
* `specialist_adjacency`: Portfolios tracking adjacent sectors to measure horizontal Strategic Diffusion ($D$).
* `active_broad`: Multi-sector active funds used to detect Thematic Graduation.
* `implementation_etf`: Highly liquid instruments used for direct vehicle execution, options overlays, or short hedging legs.
* `broad_passive_control`: Market-cap index benchmarks (`QQQ`, `SPY`, `IWM`, `IEF`) used to compute Active Weight ($w_{\text{active}}$) and strip out market drift.

### 2.3 The 8-Factor Fund Quality Scoring Model ($FundQuality_f$)
Each fund receives an aggregate score ($0.0$ to $1.0$) calculated as:
$$FundQuality_f = \sum_{k} w_k \cdot \text{Meta}_k$$

| Parameter | Default Weight ($w_k$) | Description |
| :--- | :---: | :--- |
| `mandate_relevance` | 0.25 | Alignment with target strategic theme. |
| `activeness` | 0.20 | Degree of active management vs. passive index tracking. |
| `manager_independence` | 0.15 | Operational autonomy of the portfolio management team. |
| `disclosure_quality` | 0.10 | Consistency, timeliness, and completeness of daily reporting. |
| `portfolio_concentration` | 0.10 | Conviction weighting (high active share vs. benchmark). |
| `turnover_character` | 0.05 | Information density of rebalance/trading frequency. |
| `liquidity` | 0.05 | Average daily dollar volume and options chain depth. |
| `history` | 0.10 | Track record duration of the strategy and team. |

### 2.4 Canonical JSON Schema (`fund_universe.json`)
```json
{
  "fund_id": "ETF_TICKER",
  "ticker": "TICKER",
  "name": "Full ETF Name",
  "issuer": "Issuer Name",
  "adviser": "Adviser Entity LLC",
  "subadviser": null,
  "manager_cluster_id": "MGR_UNIQUE_CLUSTER",
  "classification": "active_thematic | rules_based_thematic | specialist_adjacency | active_broad | implementation_etf | broad_passive_control",
  "transparency_regime": "fully_transparent_daily",
  "primary_theme": "theme_key",
  "eligible_functions": ["function_1", "function_2"],
  "benchmark_index": "Underlying Index Name or null",
  "rebalance_frequency": "discretionary_daily | monthly | quarterly | semi_annual | annual",
  "fund_quality_meta": {
    "mandate_relevance": 0.95,
    "activeness": 1.00,
    "manager_independence": 0.95,
    "disclosure_quality": 1.00,
    "portfolio_concentration": 0.85,
    "turnover_character": 0.80,
    "liquidity": 0.95,
    "history": 0.90
  }
}
