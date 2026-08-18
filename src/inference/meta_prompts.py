"""meta_prompts.py
Strict JSON-only prompt templates placeholder.
"""
PROMPTS = {
    "thesis": {"role": "system", "content": "{\"task\": \"generate_thesis\"}"}
}
"""## LLM Prompt Engineering & Structured Reasoning Templates (`src/inference/meta_prompts.py`)

The `meta_prompts.py` module defines structured system prompts, deterministic JSON schemas, few-shot exemplars, and chain-of-thought scaffolds for LLM-assisted qualitative reasoning within the **EDGE-TF-disclosure-agent-engine**. It enforces strict adherence to SEC regulatory disclosures (Rule 6c-11, Rule 35d-1), qualitative falsification framing, catalyst extraction, and portfolio rebalance rationale generation.

---

### Key Capabilities

* **`Thematic Hypothesis Extraction Prompt`**: Scaffolds the translation of unstructured financial text (10-K/10-Q MD&A, earnings call transcripts, product roadmaps) into machine-readable hypotheses with clear falsification boundaries.
* **`Regulatory Disclosure & Commentary Synthesizer`**: Generates factual, non-promotional ETF commentary and Portfolio Composition File (PCF) disclosure notes adhering to SEC Rule 6c-11.
* **`Adversarial Thesis Red-Teaming Prompt`**: Challenges investment proposals by generating specific downside failure modes, counter-catalysts, and risk factor mappings.
* **`JSON Output Schemas & Parsing Guardrails`**: Formats prompt inputs with explicit typing to guarantee deterministic JSON output compatible with `pydantic` or Python dataclasses.
Python"""
# src/inference/meta_prompts.py
"""
EDGE-TF Disclosure Agent Engine - Meta-Prompt Templates & Reasoning Scaffolds.

Provides structured prompt definitions, JSON schema specifications, and red-teaming
scaffolds for qualitative hypothesis generation, disclosure synthesis, and thesis falsification.
"""

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any, Dict, List, Optional


class PromptTaskType(str, Enum):
    HYPOTHESIS_DISCOVERY = "HYPOTHESIS_DISCOVERY"
    DISCLOSURE_COMMENTARY = "DISCLOSURE_COMMENTARY"
    ADVERSARIAL_RED_TEAM = "ADVERSARIAL_RED_TEAM"
    REBALANCE_RATIONALE = "REBALANCE_RATIONALE"


SYSTEM_PROMPT_CORE_FIDUCIARY = """You are an institutional ETF Research Analyst and Compliance Reasoning Engine operating within the EDGE-TF Disclosure Agent Engine framework.

Your analysis must strictly adhere to the following principles:
1. Objectivity & Falsifiability: Every qualitative thesis must have explicit, measurable invalidation criteria (drawdown caps, relative benchmark lag, catalyst failure modes).
2. Regulatory Grounding: Adhere to SEC Rule 6c-11 (ETF Transparency), Rule 35d-1 (Names Rule), and Investment Company Act fiduciary standards. All statements must be factual, balanced, and free from promotional or speculative hyperbole.
3. Structured Output: Always return strictly formatted JSON matching the requested schema. Do not enclose JSON in markdown backticks or commentary unless explicitly instructed.
"""


# ----------------------------------------------------------------------
# 1. Qualitative Hypothesis & Catalyst Discovery Meta-Prompt
# ----------------------------------------------------------------------

HYPOTHESIS_DISCOVERY_USER_TEMPLATE = """Analyze the following corporate disclosures, earnings transcripts, or thematic industry developments to formulate structured, falsifiable investment hypotheses for candidate universe expansion.

[SOURCE TEXT]:
{source_text}

[TARGET THEMATIC CLUSTERS]:
{thematic_clusters}

[OUTPUT FORMAT REQUIREMENT]:
Generate a JSON object conforming to this schema:
{{
  "hypotheses": [
    {{
      "target_ticker": "STRING (e.g. AAPL, NVDA, TSLA)",
      "thematic_cluster": "STRING",
      "thesis_statement": "STRING (Concise 1-2 sentence core economic thesis)",
      "primary_catalyst": "STRING (One of: EARNINGS_SURPRISE, PRODUCT_CYCLE, REGULATORY_SHIFT, MACRO_REGIME, MARGIN_EXPANSION)",
      "expected_timeframe_days": INTEGER (e.g. 90),
      "conviction_score": FLOAT (0.0 to 1.0),
      "falsification_criteria": {{
        "invalidation_drawdown_pct": FLOAT (e.g. 0.12 for 12%),
        "max_underperformance_vs_benchmark_bps": FLOAT (e.g. 500.0),
        "nullification_catalyst": "STRING (Specific observable operational failure)"
      }}
    }}
  ]
}}
"""


# ----------------------------------------------------------------------
# 2. Adversarial Red-Teaming & Falsification Meta-Prompt
# ----------------------------------------------------------------------

ADVERSARIAL_RED_TEAM_USER_TEMPLATE = """You are an adversarial risk officer tasked with stress-testing and attempting to falsify the following investment proposal. Identify critical points of failure, counter-theses, and non-linear risk factors.

[PROPOSED ASSET]: {ticker}
[PROPOSED THESIS]: {thesis_statement}
[PRIMARY CATALYST]: {primary_catalyst}
[PROPOSED WEIGHT]: {proposed_weight_pct}%

[TASK]:
Produce a rigorous adversarial challenge detailing 3 distinct falsification scenarios and assign an institutional vulnerability score (0.0 = completely robust, 1.0 = highly vulnerable).

[OUTPUT JSON SCHEMA]:
{{
  "ticker": "{ticker}",
  "vulnerability_score": FLOAT (0.0 to 1.0),
  "primary_failure_mode": "STRING",
  "counter_theses": [
    {{
      "scenario_name": "STRING",
      "probability": "STRING (LOW, MEDIUM, HIGH)",
      "invalidation_trigger": "STRING",
      "impact_description": "STRING"
    }}
  ],
  "recommendation": "STRING (PROCEED, ADJUST_WEIGHT, or REJECT)"
}}
"""


# ----------------------------------------------------------------------
# 3. SEC Rule 6c-11 Daily Rebalance & Disclosure Commentary Prompt
# ----------------------------------------------------------------------

DISCLOSURE_COMMENTARY_USER_TEMPLATE = """Synthesize daily Portfolio Composition File (PCF) disclosure notes and rebalance commentary for Authorized Participants (APs), fund auditors, and public regulatory release.

[FUND NAME]: EDGE-TF Thematic Growth ETF
[DATE]: {date_utc}
[TARGET CONSTITUENT WEIGHTS]:
{target_weights_json}

[TOP BUYS / INCREASES]:
{buys_summary}

[TOP SELLS / DECREASES]:
{sells_summary}

[DERIVATIVES OVERLAY (COVERED CALLS & SHORT PUTS)]:
{derivatives_overlay_summary}

[REGULATORY COMPLIANCE STATUS]:
- IRC Subchapter M (5/50 Rule): {subchapter_m_status}
- SEC Rule 18f-4 (Relative VaR): {var_status} (Relative VaR: {relative_var}x)
- SEC Rule 22e-4 (Illiquid Assets): {illiquid_weight_pct}%
- SEC Rule 35d-1 (Names Rule): {names_rule_pct}%

[REQUIREMENTS]:
1. Provide a neutral, factual summary of the rebalance changes.
2. Explicitly note compliance across statutory gates.
3. Summarize any active options overlay positioning without speculative forward-looking guarantees.

[OUTPUT JSON SCHEMA]:
{{
  "disclosure_date_utc": "{date_utc}",
  "headline": "STRING",
  "executive_summary": "STRING (2-3 sentences)",
  "statutory_compliance_statement": "STRING",
  "portfolio_changes_summary": {{
    "net_equity_allocation_pct": FLOAT,
    "options_overlay_exposure_pct": FLOAT,
    "key_rebalance_drivers": ["STRING"]
  }},
  "risk_disclaimer": "STRING"
}}
"""


# ----------------------------------------------------------------------
# Helper Utilities & Builder Classes
# ----------------------------------------------------------------------

@dataclass
class PromptBundle:
    system_prompt: str
    user_prompt: str
    task_type: PromptTaskType


class MetaPromptBuilder:
    """Builds parameterized prompt payloads for inference execution."""

    @staticmethod
    def build_hypothesis_discovery_prompt(
        source_text: str,
        thematic_clusters: List[str]
    ) -> PromptBundle:
        user_prompt = HYPOTHESIS_DISCOVERY_USER_TEMPLATE.format(
            source_text=source_text,
            thematic_clusters=", ".join(thematic_clusters)
        )
        return PromptBundle(
            system_prompt=SYSTEM_PROMPT_CORE_FIDUCIARY,
            user_prompt=user_prompt,
            task_type=PromptTaskType.HYPOTHESIS_DISCOVERY
        )

    @staticmethod
    def build_adversarial_red_team_prompt(
        ticker: str,
        thesis_statement: str,
        primary_catalyst: str,
        proposed_weight_pct: float
    ) -> PromptBundle:
        user_prompt = ADVERSARIAL_RED_TEAM_USER_TEMPLATE.format(
            ticker=ticker,
            thesis_statement=thesis_statement,
            primary_catalyst=primary_catalyst,
            proposed_weight_pct=proposed_weight_pct
        )
        return PromptBundle(
            system_prompt=SYSTEM_PROMPT_CORE_FIDUCIARY,
            user_prompt=user_prompt,
            task_type=PromptTaskType.ADVERSARIAL_RED_TEAM
        )

    @staticmethod
    def build_disclosure_commentary_prompt(
        date_utc: str,
        target_weights: Dict[str, float],
        buys_summary: str,
        sells_summary: str,
        derivatives_overlay_summary: str,
        subchapter_m_status: str,
        var_status: str,
        relative_var: float,
        illiquid_weight_pct: float,
        names_rule_pct: float
    ) -> PromptBundle:
        user_prompt = DISCLOSURE_COMMENTARY_USER_TEMPLATE.format(
            date_utc=date_utc,
            target_weights_json=json.dumps(target_weights, indent=2),
            buys_summary=buys_summary,
            sells_summary=sells_summary,
            derivatives_overlay_summary=derivatives_overlay_summary,
            subchapter_m_status=subchapter_m_status,
            var_status=var_status,
            relative_var=relative_var,
            illiquid_weight_pct=illiquid_weight_pct,
            names_rule_pct=names_rule_pct
        )
        return PromptBundle(
            system_prompt=SYSTEM_PROMPT_CORE_FIDUCIARY,
            user_prompt=user_prompt,
            task_type=PromptTaskType.DISCLOSURE_COMMENTARY
        )


__all__ = [
    "PromptTaskType",
    "PromptBundle",
    "SYSTEM_PROMPT_CORE_FIDUCIARY",
    "HYPOTHESIS_DISCOVERY_USER_TEMPLATE",
    "ADVERSARIAL_RED_TEAM_USER_TEMPLATE",
    "DISCLOSURE_COMMENTARY_USER_TEMPLATE",
    "MetaPromptBuilder",
]
