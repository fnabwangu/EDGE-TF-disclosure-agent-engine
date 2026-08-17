# EDGE-TF v0.2 Stabilization Roadmap
**Target Status:** RESEARCH_PROTOTYPE → DETERMINISTIC_CORE_STABLE

**Version:** 0.2.0-rc.1  
**Date Created:** 2026-08-17  
**Lead:** fnabwangu  
**Approval Status:** PENDING GOVERNANCE REVIEW

---

## Executive Summary

This roadmap addresses 7 critical defects discovered during code review that prevent the system from entering production. The defects span:

1. **Syntax & Compilation Errors** (29 files with markdown contamination)
2. **Semantic Collision** (IAV calculator implements INAV instead of Institutional Adoption Velocity)
3. **Fail-Open Logic** (Multiple branches that should hard-fail instead gracefully degrade)
4. **Configuration Breakdown** (JSON schemas missing, only 1/7 config files parse)
5. **Ingestion Mismatch** (Crawler targets SEC EDGAR instead of daily ETF disclosures)
6. **Test Suite Collapse** (0 passing tests; pytest collection fails)
7. **Pipeline Isolation** (Optimizer not bound to signal flow or governance)

---

## Phase 1: Emergency Syntax Purge (Week 1-2)

### 1.1 File-by-File Markdown Cleanup

**Problem:** Every `.py` file contains embedded Markdown headers, block quotes, and template prose mixed with actual Python code. This breaks AST parsing and pytest collection.

**Affected Files** (~29 total):
- `src/quant_engine/iav_calculator.py` (lines 9-28: trailing Markdown)
- `src/ingestion/disclosure_crawler.py` (lines 17-36: MD block inside function)
- `src/governance/risk_governor.py` (lines 7-14: unescaped prose)
- All `src/*/`__init__.py` files with dangling docstrings
- `console/components/*.py`
- `tests/*.py`

**Actions:**
1. Strip all Markdown commentary and block quotes from module body
2. Preserve only valid Python docstrings (triple-quoted, top-level)
3. Relocate specification prose to `SPECIFICATIONS.md` or dedicated `.rst` files
4. Verify `python -m py_compile` on every file after cleanup
5. Run `ruff check --select E999` (syntax errors) on entire repo

**Acceptance Criteria:**
- ✅ `pytest --collect-only` completes without error
- ✅ `python -m py_compile src/ tests/ console/` exits 0
- ✅ No `SyntaxError` or `IndentationError` in any module

---

### 1.2 Dependencies & Build System Audit

**Problem:** `pyproject.toml` declares only 5 dependencies; at least 3 critical ones missing:
- `cvxpy` (convex optimization)
- `scipy` (statistical functions)
- `jsonschema` (config validation)
- `pydantic` (data validation)

**Actions:**
1. Update `pyproject.toml`:
   ```toml
   dependencies = [
       "numpy>=1.25",
       "pandas>=2.2",
       "networkx>=3.0",
       "scipy>=1.12",
       "cvxpy>=1.4",
       "streamlit>=1.24",
       "requests>=2.30",
       "pydantic>=2.0",
       "jsonschema>=4.20",
       "pytest>=7.0",
   ]
   ```
2. Run `pip install -e .` and verify no import errors
3. Lock dependencies in `requirements.txt`
4. Update `Dockerfile` to use clean Python 3.11 base

**Acceptance Criteria:**
- ✅ `pip install -e .` completes successfully
- ✅ `import src; import cvxpy; import jsonschema` all succeed
- ✅ Docker image builds without warnings

---

## Phase 2: Critical Semantic Fixes (Week 2-3)

### 2.1 Resolve IAV / INAV Collision

**Problem:** 
- `src/quant_engine/iav_calculator.py` (246 lines) implements **Indicative Intra-Day Value (INAV / Rule 6c-11)** — the ETF issuer's creation unit pricing logic
- It should instead implement **Institutional Adoption Velocity (IAV)** — the multi-factor signal aggregator
- The confusion causes INAV calculations to corrupt IAV scores downstream

**Root Cause:** During scaffolding, a template with INAV pricing logic was incorrectly placed in the quant engine module.

**Actions:**

**Step 1: Create `src/fund_operations/` module**
```
src/fund_operations/
├── __init__.py
└── indicative_nav.py  (Rule 6c-11 implementation)
```

**Step 2: Move INAV to `src/fund_operations/indicative_nav.py`**
- Relocate all `IAVCalculator`, `OptionPositionState`, `IAVSnapshot` classes
- Refactor class name to `Intraday​NavCalculator` to reduce confusion
- Add module docstring: "SEC Rule 6c-11 Indicative Intra-Day Value (INAV) calculations for authorized participant operations"

**Step 3: Rebuild `src/quant_engine/iav_calculator.py` (Institutional Adoption Velocity)**

```python
"""Institutional Adoption Velocity (IAV) multi-factor signal aggregator.

Implements the EDGE-TF proprietary composite signal:
    IAV_composite = Σ βₖ Zₖ - Σ λⱼ Penaltyⱼ

Where factors Z are:
    I: Weighted New Discretionary Initiations
    Q: Active Quantity Deviation (AQD)
    B: Deduplicated Independent-Manager Breadth Delta
    D: Strategic Theme Diffusion
    P: Exponentially Weighted Persistence (δ^τ)
    C: Within-Fund Conviction / Active Weight Shift

Subject to penalties for:
    - Coincident rebalancing (index reconstitution)
    - High manager HHI (concentration)
    - Stale data or missed observations
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

@dataclass
class QuantitativeSignalPayload:
    """Typed output of IAV computation."""
    timestamp_utc: datetime
    security_ticker: str
    composite_iav_score: float  # [-1.0, 1.0] normalized
    component_scores: Dict[str, float]  # {'I': ..., 'Q': ..., 'B': ..., ...}
    confidence_pct: float  # [0, 100]
    persistence_decay_factor: float  # δ^τ
    sample_depth: int  # Number of observations included
    falsification_status: str  # PENDING, PASSED, FAILED
    data_quality_flags: List[str]  # Warnings/issues


class InstitutionalAdoptionVelocityEngine:
    """Multi-factor Institutional Adoption Velocity signal generator."""
    
    def __init__(self):
        """Initialize with policy defaults."""
        self.beta_weights = {
            'initiations': 0.30,
            'aqd': 0.25,
            'breadth': 0.20,
            'diffusion': 0.15,
            'persistence': 0.10,
        }
        self.penalty_weights = {
            'rebalance_coincidence': 0.50,
            'manager_hhi': 0.30,
            'data_staleness': 0.20,
        }
    
    def compute_iav(
        self,
        security_ticker: str,
        initiations_score: float,
        aqd_score: float,
        breadth_delta: int,
        theme_diffusion: float,
        persistence_vector: np.ndarray,
        conviction_shift: float,
        penalties: Dict[str, float],
        sample_observations: int,
        observation_window_days: int,
    ) -> QuantitativeSignalPayload:
        """
        Compute composite IAV score from component factors.
        
        Returns QuantitativeSignalPayload with typed, auditable result.
        """
        # Normalize component scores to [-1, 1]
        Z_I = max(-1.0, min(1.0, initiations_score))
        Z_Q = max(-1.0, min(1.0, aqd_score))
        Z_B = max(-1.0, min(1.0, breadth_delta / 10.0))  # Scale breadth to [-1, 1]
        Z_D = max(-1.0, min(1.0, theme_diffusion))
        Z_P = np.mean(persistence_vector) if len(persistence_vector) > 0 else 0.0
        Z_C = max(-1.0, min(1.0, conviction_shift))
        
        component_scores = {
            'I_initiations': Z_I,
            'Q_aqd': Z_Q,
            'B_breadth': Z_B,
            'D_diffusion': Z_D,
            'P_persistence': Z_P,
            'C_conviction': Z_C,
        }
        
        # Composite numerator
        composite = (
            self.beta_weights['initiations'] * Z_I +
            self.beta_weights['aqd'] * Z_Q +
            self.beta_weights['breadth'] * Z_B +
            self.beta_weights['diffusion'] * Z_D +
            self.beta_weights['persistence'] * Z_P
        )
        
        # Apply penalties (subtract)
        for penalty_name, penalty_val in penalties.items():
            if penalty_name in self.penalty_weights:
                composite -= self.penalty_weights[penalty_name] * penalty_val
        
        # Confidence decreases with short observation windows
        confidence_pct = min(100.0, 50.0 + (sample_observations / 20.0) * 50.0)
        
        return QuantitativeSignalPayload(
            timestamp_utc=datetime.utcnow(),
            security_ticker=security_ticker,
            composite_iav_score=max(-1.0, min(1.0, composite)),
            component_scores=component_scores,
            confidence_pct=confidence_pct,
            persistence_decay_factor=Z_P,
            sample_depth=sample_observations,
            falsification_status='PENDING',
            data_quality_flags=[],
        )
```

**Acceptance Criteria:**
- ✅ `from src.fund_operations import Intraday​NavCalculator` works
- ✅ `from src.quant_engine import InstitutionalAdoptionVelocityEngine` works
- ✅ INAV is no longer mixed with IAV in any module
- ✅ No circular imports

---

### 2.2 Fail-Closed Governance Hard Invariants

**Problem:** Multiple logic branches currently fail open (graceful degradation) instead of hard-failing. This violates production governance requirements.

**Locations & Fixes:**

#### 2.2.1 `src/quant_engine/flow_decomposition.py`
**Issue:** Falls back to raw shares `q` if ETF shares outstanding `N` missing

**Current Code:**
```python
u = q / N  # Crashes if N is None
```

**Fixed Code:**
```python
if N is None or N <= 0:
    # FAIL CLOSED: Cannot compute unit shares without fund universe
    return QuantErrorPayload(
        state="DATA_QUALITY_EXCEPTION",
        reason="Missing or invalid shares outstanding: N",
        aqd_value=np.nan,
        is_valid=False,
    )
u = q / N
```

#### 2.2.2 `src/quant_engine/manager_graph.py`
**Issue:** Falls back to treating unresolved managers as independent (inflates breadth)

**Fix:** Create shared `UNRESOLVED_CLUSTER` node
```python
if adviser_cluster_id is None:
    # Do NOT treat as independent; use sentinel cluster
    adviser_cluster_id = "UNRESOLVED_CLUSTER"
    logging.warning(f"Manager {mgr_id} has no cluster; mapped to {adviser_cluster_id}")
```

#### 2.2.3 `src/ingestion/normalizer.py`
**Issue:** If baseline observation missing, fills with zero (falsely inflates share change)

**Fix:** Detect and quarantine
```python
if t_prev_shares is None:
    # FAIL CLOSED: Baseline periods cannot generate valid signals
    observation.state = "BASELINE_INITIALIZATION"
    observation.aqd = np.nan
    observation.is_valid_for_signals = False
```

#### 2.2.4 `src/governance/risk_governor.py`
**Issue:** If `config/risk_parameters.json` load fails, silently uses defaults

**Fix:** Hard fail
```python
try:
    config = json.load(f)
except Exception as exc:
    raise GovernanceConfigurationError(
        f"CRITICAL: risk_parameters.json failed to load: {exc}. "
        "System state: NO_TRADE_PERMISSIBLE."
    ) from exc
```

**Acceptance Criteria:**
- ✅ All `DATA_QUALITY_EXCEPTION` observations quarantined from downstream analysis
- ✅ Config load failure raises exception (not warning)
- ✅ `test_fail_closed_invariants.py` passes (5 cases)

---

## Phase 3: Configuration Bundle Rebuild (Week 3-4)

### 3.1 JSON Schema Definitions

**Problem:** 7 config files exist but only 1 validates. Schemas missing entirely.

**Actions:**

Create `config/schemas/` directory with:

1. **`config/schemas/fund_universe.schema.json`** (Already partially present; validate)
2. **`config/schemas/data_sources.schema.json`** — Validates rate limits, caching, provider hierarchy
3. **`config/schemas/manager_clusters.schema.json`** — Validates manager relationships
4. **`config/schemas/strategy_ontology.schema.json`** — Validates theme mappings
5. **`config/schemas/risk_parameters.schema.json`** — Validates risk thresholds
6. **`config/schemas/governance_policy.schema.json`** — Validates hard limits
7. **`config/schemas/execution_routing.schema.json`** — Validates broker routing rules

**Example: `risk_parameters.schema.json`**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Risk Governance Parameters",
  "type": "object",
  "required": [
    "subchapter_m_single_issuer_cap",
    "subchapter_m_aggregate_cap",
    "rule_18f4_relative_var_limit",
    "rule_22e4_illiquid_cap",
    "rule_35d1_names_rule_floor"
  ],
  "properties": {
    "subchapter_m_single_issuer_cap": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "description": "Single issuer weight limit under ICA Rule 2a-7"
    },
    "rule_18f4_relative_var_limit": {
      "type": "number",
      "minimum": 0.5,
      "maximum": 10.0,
      "description": "Relative VaR limit as multiple of Portfolio VaR"
    }
  }
}
```

### 3.2 Populate Valid Config Defaults

**Actions:**
1. Create `src/governance/config_loader.py` with validation logic
2. Verify all 7 JSON files pass `jsonschema.validate()` on startup
3. Add health check endpoint that validates config bundle

**Example Loader:**
```python
import jsonschema
from pathlib import Path

class ConfigurationLoader:
    def __init__(self, config_dir: Path = Path("config")):
        self.config_dir = config_dir
        self.schemas_dir = config_dir / "schemas"
    
    def validate_all(self):
        """Validate complete config bundle against schemas."""
        config_files = [
            "fund_universe.json",
            "data_sources.json",
            "risk_parameters.json",
            # ... others
        ]
        
        results = {}
        for fname in config_files:
            config_file = self.config_dir / fname
            schema_file = self.schemas_dir / f"{fname.replace('.json', '.schema.json')}"
            
            try:
                with open(config_file) as cf, open(schema_file) as sf:
                    config = json.load(cf)
                    schema = json.load(sf)
                    jsonschema.validate(config, schema)
                    results[fname] = {"status": "VALID"}
            except jsonschema.ValidationError as e:
                results[fname] = {"status": "INVALID", "error": str(e)}
                raise
        
        return results
```

**Acceptance Criteria:**
- ✅ All 7 JSON files load without error
- ✅ All 7 files pass schema validation
- ✅ `pytest tests/test_config_integrity.py` passes

---

## Phase 4: Ingestion Pipeline Refactor (Week 4-5)

### 4.1 Daily ETF Disclosures vs. SEC EDGAR

**Problem:** `src/ingestion/disclosure_crawler.py` targets corporate filings (10-K, 10-Q, Form 4) instead of the primary input: daily ETF portfolio files.

**Current Scope:**
- SEC EDGAR filings (company 10-K/10-Q)
- Intended only for supplementary alternative research

**Required Scope:**
- **Daily ETF portfolio holdings files** (CSV, XML, JSON from ETF provider sites)
- **Daily reported shares outstanding** (Nf,t) from ETF NAV feeds
- **Rule 6c-11 creation/redemption basket files** (Bf,t) from provider APIs

**Actions:**

Create `src/ingestion/etf_disclosure_fetcher.py`:

```python
"""Daily ETF portfolio disclosure ingestion (primary data source)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

@dataclass
class DualTimestampedDisclosure:
    """Holdings record with point-in-time dual timestamps."""
    etf_ticker: str
    portfolio_effective_date: datetime  # Date the portfolio represents
    information_available_time: datetime  # When file was published/crawled
    holdings: List[Dict[str, float]]  # [{'ticker': 'AAPL', 'shares': 50000}, ...]
    shares_outstanding: float  # Nf,t
    nav_per_share: float
    basket_components: Optional[List[Dict]] = None  # Creation basket Bf,t


class ETFDisclosureFetcher:
    """Ingests daily ETF holdings from provider APIs and normalization endpoints."""
    
    def fetch_etf_holdings(
        self,
        etf_ticker: str,
        provider: str = "iShares",  # Provider API (iShares, Vanguard, SPDR, etc.)
    ) -> DualTimestampedDisclosure:
        """Fetch latest portfolio disclosure with dual timestamps."""
        # Implementation: Call provider API
        # - iShares: holdings CSV from ishares.com
        # - Vanguard: holdings.xml from vanguard.com
        # - SPDR: holdings.csv from spdrs.com
        # - Schwab ETF: JSON from schwab.com/api
        pass
    
    def enforce_point_in_time(
        self,
        disclosure: DualTimestampedDisclosure,
        decision_time: datetime,
    ) -> bool:
        """Enforce: decision_time >= information_available_time (no look-ahead)."""
        if decision_time < disclosure.information_available_time:
            raise LookAheadViolationError(
                f"Decision at {decision_time} uses data only available at "
                f"{disclosure.information_available_time}"
            )
        return True
```

Update `src/ingestion/normalizer.py` to:
1. Accept dual-timestamped disclosures
2. Compute basket divergence: `||Hf,t - Bf,t||` (deviation of holdings from creation basket)
3. Enforce point-in-time invariant
4. Identify coincident rebalancing (index reconstitution dates)

**Acceptance Criteria:**
- ✅ Daily ETF holdings ingest without error (test with 10 real ETFs)
- ✅ Dual timestamps enforced (no look-ahead violations)
- ✅ Basket divergence calculated
- ✅ Index rebalance dates detected

---

## Phase 5: Deterministic Test Suite (Week 5-6)

### 5.1 Create `tests/test_deterministic_gates.py` (Extended)

**Test Cases:**

```python
def test_creation_flow_scaling():
    """20% ETF creation event; verify AQD = 0.0 (no active accumulation signal)."""
    # Setup: ETF with 10M shares, constituent position 50k shares
    # Event: +2M shares created → constituent scaled 50k → 60k (mechanical)
    # Expected: AQD = 0.0, no signal
    pass

def test_duplicate_manager_cluster():
    """3 funds with same manager_cluster_id; verify manager breadth B = 1."""
    # Setup: 3 funds, all managed by Blackrock Index Advisors
    # Expected: Manager HHI = 1.0, breadth delta = 0 (no independent confirmation)
    pass

def test_rebalance_window_coincidence():
    """Active share jump coinciding with index reconstitution; verify falsification rejects."""
    # Setup: Russell reconstitution window + 15% share increase
    # Expected: falsification_passed = False, reason = COINCIDES_WITH_SCHEDULED_INDEX_REBALANCE
    pass

def test_point_in_time_enforcement():
    """Disclosure with InformationAvailableTime > DecisionTime; verify rejection."""
    # Setup: Decision at 9:00 AM, disclosure available at 10:00 AM
    # Expected: LookAheadViolationError raised
    pass

def test_deterministic_gate_failure():
    """falsification_passed = False; verify evaluate_deterministic_gates outputs NO_TRADE_PERMISSIBLE."""
    # Setup: Falsification fails for unknown reason
    # Expected: system_state = "NO_TRADE_PERMISSIBLE"
    pass
```

### 5.2 Acceptance Criteria

- ✅ `pytest tests/test_deterministic_gates.py -v` all green (5/5 passing)
- ✅ `pytest tests/test_quant_engine.py -v` all green
- ✅ `pytest tests/test_ingestion.py -v` all green (new)
- ✅ `pytest --cov=src` ≥ 70% coverage on critical modules

---

## Phase 6: Pipeline Integration & Convex Optimizer (Week 6-7)

### 6.1 End-to-End Signal Flow

**Workflow:**
```
IAV Payload 
  ↓ (component scores, confidence)
Falsification Engine
  ↓ (reject or pass)
Implementation Fit Score 
  ↓ (multi-factor vehicle scoring)
Convex Optimizer
  ↓ (position sizing, constraint satisfaction)
Risk Governor
  ↓ (statutory gate sweep)
Pre-Trade Audit
  ↓
Execution Gateway (or NO_TRADE_PERMISSIBLE)
```

### 6.2 Optimizer Enhancements (`src/trade_design/convex_optimizer.py`)

**Objective:**
```
min_x ||Bx - τ||²_W + λ x^T Σ x + κ Σ c_i |x_i - x_{i,0}|
```

**Constraints:**
- Full investment: Σ xi ≤ 1.0
- Single position bound: 0 ≤ xi ≤ x_max
- ADV liquidity: xi · PortfolioCapital ≤ α · ADVi
- Mandate alignment: Σ xi (aligned) ≥ mandate_floor

**Fail-Closed Result:**
```python
if optimizer_status not in [cvxpy.OPTIMAL, cvxpy.OPTIMAL_INACCURATE]:
    return TradeDesignResult(
        vehicles=[],
        system_state="NO_TRADE_PERMISSIBLE",
        reason=f"Optimizer failed with status: {optimizer_status}"
    )
```

**Acceptance Criteria:**
- ✅ Optimizer integrates without circular dependencies
- ✅ Infeasible constraints → NO_TRADE_PERMISSIBLE (not fallback)
- ✅ Test suite confirms end-to-end flow (5+ scenarios)

---

## Phase 7: Release Candidate Bundle (Week 7-8)

### 7.1 Checklist Before v0.2.0-rc.1

- [ ] All 29 files compile without syntax errors
- [ ] Dependencies declared in pyproject.toml + requirements.txt
- [ ] All 7 JSON config files pass schema validation
- [ ] IAV / INAV separation complete; no imports mix the two
- [ ] Fail-closed hard invariants enforced (5 locations tested)
- [ ] Daily ETF disclosure ingestion implemented
- [ ] Dual timestamps enforced (point-in-time test passing)
- [ ] Index rebalance detection working
- [ ] Pytest suite: ≥15 passing tests, ≥70% coverage
- [ ] Docker build succeeds
- [ ] README updated with accurate module descriptions
- [ ] SPECIFICATIONS.md created (extracted from docstrings)
- [ ] Audit logger tested with sample payloads
- [ ] Kill switch integration confirmed
- [ ] Pre-trade audit flow end-to-end validated

### 7.2 Governance Review Gate

Before promotion to `PROD`:
1. ✅ Complete regression test suite (historical replay)
2. ✅ Code review by quant + compliance teams
3. ✅ Security scan (no secrets in configs)
4. ✅ Performance benchmark (latency <100ms per signal)
5. ✅ Documentation complete & reviewed
6. ✅ Rollback plan documented
7. ✅ Sign-off from Risk Governance

---

## Timeline & Milestones

| Phase | Weeks | Milestone |
|-------|-------|-----------|
| 1. Syntax Purge | 1-2 | All files compile; pytest collects |
| 2. Semantic Fixes | 2-3 | IAV/INAV separated; fail-closed enforced |
| 3. Config Rebuild | 3-4 | All 7 JSON files valid + schemas |
| 4. Ingestion Refactor | 4-5 | Daily ETF disclosure fetcher live |
| 5. Test Suite | 5-6 | ≥15 passing tests; ≥70% coverage |
| 6. Pipeline Integration | 6-7 | End-to-end flow validated |
| 7. Release Candidate | 7-8 | v0.2.0-rc.1 ready for review |

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Markdown cleanup introduces new syntax errors | Peer review all changes; run py_compile after each file |
| IAV/INAV migration breaks downstream | Add integration tests before/after; maintain backward compat shims |
| Config validation too strict | Start with warnings; promote to errors incrementally |
| Ingestion fails with real ETF APIs | Implement mock fixtures; test with 5 real ETFs before going live |
| Test coverage gaps | Mandatory review of coverage reports; flag uncovered branches |

---

## Sign-Off

**Status:** PENDING  
**Prepared by:** fnabwangu  
**Next Review:** 2026-08-24 (end of Week 1 checkpoint)

