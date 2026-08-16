```python
# ==============================================================================
# EDGE-TF™ SYSTEM CONFIGURATION AND POLICY REGISTRY
# PSEUDO-PYTHON README SPECIFICATION
# ==============================================================================
#
# REPOSITORY PATH:
#     config/README.md
#
# DOCUMENT STYLE:
#     Narrative system documentation expressed as color-coded pseudo-Python.
#
# IMPORTANT:
#     This file is intentionally formatted as one Python code block so that
#     GitHub, GitLab, VS Code, and other Markdown renderers apply syntax
#     highlighting to the complete specification.
#
#     This document is NOT intended to be imported or executed as Python.
#     It uses Python-like structures to make policies, rules, relationships,
#     and operating sequences easier to scan and reason about.
#
# ==============================================================================


# ==============================================================================
# 0. READER ORIENTATION
# ==============================================================================

SYNTAX_HIGHLIGHTING_NOTE = """
This README is a Markdown document presented as pseudo-Python.

The syntax is intentionally designed to receive color highlighting from the
reader's editor or repository browser:

    - Comments describe architecture and rationale.
    - Strings contain human-readable narrative.
    - Dictionaries group related policy fields.
    - Tuples define ordered rules, workflows, and enumerations.
    - Booleans represent eligibility or enforcement states.
    - Functions illustrate system behavior.
    - Class-like names describe conceptual system components.

The exact rendered colors depend on the user's editor theme.

The semantic color markers below remain visible regardless of theme.
"""


SEMANTIC_COLOR_LEGEND = {
    "🟦 ARCHITECTURE": (
        "System structure, component boundaries, and design principles."
    ),
    "🟩 PERMITTED": (
        "Allowed behavior, eligible actions, or approved workflow states."
    ),
    "🟨 WARNING": (
        "A condition that requires review, penalty, or elevated caution."
    ),
    "🟥 HARD VETO": (
        "A condition that blocks production action or execution."
    ),
    "🟪 AGENT": (
        "Inference-agent permissions, proposals, and reasoning boundaries."
    ),
    "🟧 HUMAN GATE": (
        "A required approval, escalation, or governance review."
    ),
    "🟫 AUDIT": (
        "Provenance, reproducibility, immutable history, and traceability."
    ),
    "⬜ NARRATIVE": (
        "Explanatory material intended for human readers."
    ),
}


REGISTRY_METADATA = {
    "repository_path": "config/README.md",
    "registry_version": "2.0.0-rc.1",
    "schema_version": "2.0.0",
    "status": "RELEASE CANDIDATE",
    "last_updated": "2026-08-16",
    "configuration_owner": "EDGE-TF Research Governance",
    "runtime_access": "READ ONLY",
    "document_mode": "COLOR-CODED PSEUDO-PYTHON",
}


PROMOTION_NOTICE = """
🟨 RELEASE CANDIDATE NOTICE

Promote this registry bundle to `PROD` only after:

    1. Every referenced configuration file exists.
    2. Every JSON file passes schema validation.
    3. Every cross-file invariant passes.
    4. Historical regression tests pass.
    5. Point-in-time replay tests pass.
    6. Governance and kill-switch tests pass.
    7. The complete manifest has been generated.
    8. File hashes have been verified.
    9. Required human approvals have been recorded.
   10. The release bundle has been signed.
   11. A valid rollback target has been established.

Until those conditions are satisfied, this registry describes the intended
production contract but does not represent a fully promoted production release.
"""


README_PURPOSE = """
⬜ WHAT THIS FILE IS

This README is the human-readable constitution for the EDGE-TF configuration
registry.

It explains:

    - What belongs in `config/`.
    - What must remain outside `config/`.
    - Which files control which decisions.
    - How ETF disclosure sources become eligible.
    - How funds are classified and assigned system roles.
    - How securities are mapped to strategies and business functions.
    - How Institutional Adoption Velocity is governed.
    - How model scores interact with deterministic risk policy.
    - What agents may propose.
    - What agents are prohibited from doing.
    - When human approval is mandatory.
    - How every decision is reconstructed after the fact.
    - How a configuration change reaches production.
    - How production is stopped when confidence in data or controls fails.

This README is deliberately detailed.

The system is intended to move from a research methodology into a software
architecture capable of supporting agent-assisted trade research, trade design,
risk review, and controlled execution.

That transition requires the governing assumptions to be explicit before they
become code.
"""


README_IS_NOT = """
⬜ WHAT THIS FILE IS NOT

This README is not:

    - A live market-data file.
    - A holdings database.
    - A feature store.
    - A broker configuration containing credentials.
    - A substitute for JSON Schema.
    - A substitute for unit tests.
    - A substitute for governance approval.
    - A substitute for investment judgment.
    - A guarantee that the model is correct.
    - A guarantee that a trade will be profitable.
    - Authorization for an agent to execute an order.
    - A place to store mutable runtime state.

The README explains the contract.

The normative JSON files, schemas, signed manifest, runtime data, and audit
records implement that contract.
"""


INTENDED_AUDIENCES = {
    "researcher": (
        "Uses disclosures, ontology mappings, and model outputs to study "
        "institutional adoption."
    ),
    "quant_engineer": (
        "Implements point-in-time ingestion, features, scoring, testing, and "
        "reproducible calculation."
    ),
    "data_engineer": (
        "Maintains sources, raw artifacts, normalization, provenance, and "
        "quality controls."
    ),
    "risk_governance": (
        "Defines hard limits, veto conditions, escalation rules, and release "
        "approval requirements."
    ),
    "execution_engineer": (
        "Implements deterministic pre-order checks and broker interaction."
    ),
    "ontology_reviewer": (
        "Reviews business-function mappings and prevents classification drift."
    ),
    "agent_designer": (
        "Builds prompts and tools that operate within explicit permissions."
    ),
    "auditor": (
        "Reconstructs which data, configuration, model, prompt, approval, and "
        "order state produced a decision."
    ),
}


HOW_TO_READ_THIS_FILE = """
⬜ RECOMMENDED READING ORDER

A first-time reader should move through this document in the following order:

    Step 1:
        Read Sections 1 through 3 to understand the system's purpose,
        authority, and governing principles.

    Step 2:
        Read Sections 4 through 8 to understand the configuration bundle,
        fund registry, and disclosure-source controls.

    Step 3:
        Read Sections 9 through 12 to understand manager independence,
        strategy ontology, holdings purity, and Institutional Adoption
        Velocity.

    Step 4:
        Read Sections 13 through 18 to understand governance, point-in-time
        integrity, data quality, environment profiles, and agent permissions.

    Step 5:
        Read Sections 19 through 24 to understand auditability, release
        management, operations, and failure behavior.

    Step 6:
        Read Sections 25 through 30 before enabling production access.

A developer implementing only one module should still read the authority,
failure, and audit sections.

Local correctness is not enough if the complete decision cannot be governed
and reproduced.
"""


ONE_MINUTE_MENTAL_MODEL = """
⬜ THE ONE-MINUTE VERSION

EDGE-TF observes how ETF portfolios change.

It does not assume that a large portfolio weight is automatically a useful
signal.

It asks whether:

    - A new position appeared.
    - Actual shares increased.
    - Multiple independent managers acted.
    - A business function is spreading across relevant funds.
    - The pattern persisted.
    - The security still has room for future adoption.
    - The signal survives alternative explanations.
    - A trade can be designed with suitable purity, liquidity, duration, and
      downside control.
    - Governance permits the proposed implementation.

The system then records exactly:

    - What information was known.
    - When it became known.
    - Which configuration governed the analysis.
    - Which model and prompts were used.
    - Which vetoes, warnings, and approvals applied.
    - What final action was taken.

The desired result is not blind automation.

The desired result is structured, explainable, auditable decision support.
"""


SYSTEM_TRUST_MODEL = """
⬜ TRUST MODEL

EDGE-TF does not place unconditional trust in any single component.

It does not fully trust:

    - One ETF.
    - One issuer file.
    - One manager.
    - One ticker.
    - One ontology label.
    - One model score.
    - One options-flow signal.
    - One agent response.
    - One human conclusion.
    - One broker response.

Trust is assembled through layered controls:

    DATA TRUST
        Was the correct artifact collected?
        Was it complete?
        Was it available at the relevant time?
        Was it parsed correctly?
        Was the original preserved?

    CLASSIFICATION TRUST
        Does the fund genuinely map to the theme?
        Does the company perform the claimed business function?
        Is the mapping current and independently reviewed?

    SIGNAL TRUST
        Did shares change?
        Did independent managers act?
        Did the pattern persist?
        Is the movement distinguishable from price drift or index mechanics?

    VALIDATION TRUST
        Do fundamentals, liquidity, valuation, market structure, and other
        evidence support or contradict the thesis?

    GOVERNANCE TRUST
        Does the trade remain inside deterministic policy?

    EXECUTION TRUST
        Is the instrument valid, liquid, approved, and consistent with the
        current portfolio and broker state?

    AUDIT TRUST
        Can the complete decision be reconstructed without guesswork?
"""


# ==============================================================================
# 1. EXECUTIVE SUMMARY
# ==============================================================================

EXECUTIVE_SUMMARY_NARRATIVE = """
⬜ WHY THE CONFIGURATION REGISTRY EXISTS

A research engine can survive informal assumptions.

A production trading architecture cannot.

Once research logic begins influencing position sizing, option selection,
portfolio exposure, or broker orders, every assumption becomes operational.

The purpose of `config/` is to make those assumptions explicit and versioned.

The registry separates durable declarations from changing observations.

Durable declarations include:

    - The identity of a fund.
    - The role a fund may perform.
    - The source expected to publish its holdings.
    - The ontology functions to which its mandate may relate.
    - The model formula and policy version.
    - The maximum risk the system is allowed to accept.
    - The approvals required before execution.

Changing observations include:

    - Today's holdings.
    - Today's share counts.
    - Today's fund assets.
    - Today's liquidity.
    - Today's options open interest.
    - Today's Institutional Adoption Velocity.
    - Today's adoption stage.
    - Today's portfolio exposures.

Those observations belong in runtime data stores.

The registry tells runtime systems how to interpret and govern those
observations.
"""


EXECUTIVE_SUMMARY = """
The `config/` directory is the normative configuration registry for the
EDGE-TF™ research, trade-design, risk-governance, and execution architecture.

It defines:

1. The registered institutional ETF universe.
2. The permitted roles each ETF may perform inside the system.
3. The Strategy-First Ontology used to map securities to business functions
   and investment strategies.
4. The quantitative model policies used to calculate Institutional Adoption
   Velocity and related signals.
5. The deterministic governance rules that can constrain or veto a proposed
   trade.
6. The source, timestamp, data-quality, and provenance requirements governing
   every signal.
7. The environment-specific controls for research, paper, and production
   operation.
8. The agent permissions, human-approval gates, audit requirements, and release
   procedures required for safe operation.

The registry does not contain live holdings, current liquidity measurements,
market prices, broker credentials, account identifiers, API secrets, or other
runtime data.

Released configuration bundles are immutable.

Any modification requires a new versioned release.
"""


SYSTEM_DESIGN_PROMISE = """
🟦 ARCHITECTURAL PROMISE

Every downstream calculation in:

    src/quant_engine/
    src/inference/
    src/validation/
    src/trade_design/
    src/governance/
    src/execution/

SHOULD be reproducibly connected to a validated configuration snapshot.

The software should be able to answer:

    - Which configuration bundle governed this decision?
    - Which fund universe was active?
    - Which sources were eligible?
    - Which ontology version classified the exposure?
    - Which model policy calculated the signal?
    - Which governance policy sized or vetoed the trade?
    - Which environment profile was active?
    - Which human approval was required?
    - Which order packet reached the broker?

If the system cannot answer those questions, it is not production-auditable.
"""


# ==============================================================================
# 2. CORE ARCHITECTURAL PRINCIPLE
# ==============================================================================

CORE_ARCHITECTURAL_PRINCIPLE_NARRATIVE = """
⬜ FROM HOLDINGS LIST TO STRATEGY INTELLIGENCE

Most ETF tools begin and end with a snapshot.

They show:

    - A ticker.
    - A holding.
    - A weight.
    - A rank.
    - A current portfolio.

EDGE-TF is designed around movement rather than snapshots.

A current holding is evidence of ownership.

It is not automatically evidence of:

    - New conviction.
    - Increasing conviction.
    - Strategic adoption.
    - Manager accumulation.
    - Independent confirmation.
    - Future return.

A security can become a large holding because its price rose.

A security can remain a small holding while multiple relevant managers begin
building positions.

The second pattern may contain more information about ownership formation than
the first.

For this reason, the system reads disclosures as time-series evidence.

The object of analysis is not merely what a fund owns.

The object of analysis is how capital organization changes across time,
managers, mandates, functions, and implementation vehicles.
"""


CORE_ARCHITECTURAL_PRINCIPLE = """
EDGE-TF treats ETF disclosures as public strategy records.

The system does not begin by asking:

    What are the largest ETF holdings?

It begins by asking:

    Which strategies, business functions, and securities are moving through
    the institutional adoption cycle?
"""


ANALYTICAL_SEQUENCE = (
    "Collect",
    "Normalize",
    "Classify",
    "Compare",
    "Score",
    "Validate",
    "Design",
    "Govern",
    "Execute",
    "Monitor",
)


ANALYTICAL_SEQUENCE_EXPLANATION = {
    "Collect": (
        "Acquire the correct disclosure artifact and preserve the original."
    ),
    "Normalize": (
        "Resolve identifiers, dates, units, currencies, and source-specific "
        "formats."
    ),
    "Classify": (
        "Map funds and securities into themes, business functions, and roles."
    ),
    "Compare": (
        "Measure change across time, funds, managers, and strategic categories."
    ),
    "Score": (
        "Calculate adoption velocity, persistence, breadth, room to grow, and "
        "structural penalties."
    ),
    "Validate": (
        "Test alternative explanations and seek disconfirming evidence."
    ),
    "Design": (
        "Compare ETFs, baskets, equities, options, spreads, hedges, and "
        "`NO_TRADE`."
    ),
    "Govern": (
        "Apply deterministic limits, vetoes, and human approval gates."
    ),
    "Execute": (
        "Submit only a validated, immutable order packet through the approved "
        "execution gateway."
    ),
    "Monitor": (
        "Track disclosures, thesis health, risk state, fills, and exit logic."
    ),
}


READING_DISCIPLINE = (
    "Read the fund before the ticker.",
    "Read shares before weight.",
    "Read category before company.",
    "Read persistence before excitement.",
    "Read disconfirmation before implementation.",
)


READING_DISCIPLINE_EXPLANATION = """
⬜ WHY THESE FIVE RULES MATTER

Read the fund before the ticker:
    A holding only has meaning in the context of the fund's mandate, process,
    constraints, and strategic relevance.

Read shares before weight:
    Weight can rise without manager buying. Share-count change is closer to
    observable manager action, although it still requires flow and
    corporate-action adjustment.

Read category before company:
    The company is an implementation of a strategic function. Starting with
    the function reduces ticker-chasing and clarifies what exposure is
    actually being purchased.

Read persistence before excitement:
    One observation is a clue. Repeated, independent, time-consistent behavior
    is stronger evidence.

Read disconfirmation before implementation:
    The purpose of validation is not to decorate a favored trade. It is to
    determine whether capital should be withheld.
"""


# ==============================================================================
# 3. NORMATIVE AUTHORITY
# ==============================================================================

NORMATIVE_AUTHORITY_NARRATIVE = """
⬜ WHY AUTHORITY MUST BE ORDERED

Agentic systems create a specific governance risk:

Different components can produce different answers at the same time.

For example:

    - The model may assign a high signal score.
    - The inference agent may describe a compelling narrative.
    - The options agent may identify favorable convexity.
    - The risk engine may detect excessive concentration.
    - The data-quality service may detect a stale disclosure.
    - The kill switch may prohibit new options positions.

Without a defined hierarchy, software components may attempt to resolve those
conflicts informally.

That is unacceptable in production.

EDGE-TF therefore uses explicit authority precedence.

The hierarchy is intentionally asymmetric:

    - Research components may propose.
    - Governance components may constrain.
    - Emergency controls may stop.
    - Lower layers may never relax higher-layer restrictions.

This keeps intelligence and authority separate.
"""


AUTHORITY_PRECEDENCE = (
    "Emergency kill switches.",
    "Hard vetoes in `governance_policy.json`.",
    "Environment restrictions in `profiles/`.",
    "Quantitative rules in `model_policy.json`.",
    "Validated fund and source eligibility.",
    "Strategy ontology classifications.",
    "Inference-agent recommendations.",
    "Execution preferences.",
)


AUTHORITY_RULE = """
A lower-priority layer may not override a higher-priority layer.
"""


AUTHORITY_EXAMPLES = (
    "An inference agent may not override a governance veto.",
    "A production profile may tighten a risk limit but may not loosen it.",
    "A model score may not make a fund eligible if its disclosure source is "
    "unverified.",
    "A high-confidence trade thesis may not override stale-data controls.",
    "Human approval may authorize an eligible trade but may not bypass an "
    "emergency kill switch.",
)


CONFLICT_RESOLUTION_EXAMPLE = """
🟥 HARD VETO EXAMPLE

Suppose the system observes:

    signal_confidence = 0.91
    validation_confidence = 0.84
    implementation_confidence = 0.79

But also observes:

    source_status = "STALE"
    governance_result = "HARD_VETO"

The final action is:

    final_action = "NO_TRADE"

The high score remains part of the audit record.

It does not become permission.
"""


# ------------------------------------------------------------------------------
# 3.1 NORMATIVE FILES
# ------------------------------------------------------------------------------

NORMATIVE_FILES_NARRATIVE = """
⬜ README VERSUS MACHINE-ENFORCED POLICY

Human-readable prose can become stale.

Machine-readable configuration can also become stale.

The difference is that machine-readable configuration can be validated,
hashed, versioned, and loaded deterministically.

For that reason:

    - This README explains intent.
    - JSON files declare operational values.
    - JSON Schemas define allowed structure.
    - The manifest identifies the complete release.
    - Tests determine whether the bundle is internally coherent.
    - Governance approval determines whether it may enter production.

The README should never be the only place where a numeric threshold exists.

A developer should not need to manually interpret prose to discover the
maximum permitted position size or minimum required disclosure freshness.
"""


NORMATIVE_FILES = (
    "manifest.json",
    "All JSON files in the root of `config/`",
    "All schemas in `config/schemas/`",
    "The active environment profile in `config/profiles/`",
)


NORMATIVE_FILE_POLICY = """
This README is explanatory.

If this README conflicts with a validated JSON file, the validated JSON file
governs.

If two normative files conflict, the precedence rules in this README and
`governance_policy.json` govern.
"""


# ------------------------------------------------------------------------------
# 3.2 NORMATIVE LANGUAGE
# ------------------------------------------------------------------------------

NORMATIVE_LANGUAGE_NARRATIVE = """
⬜ WHY CONTROL WORDS ARE FORMALIZED

Words such as "should," "must," and "may" are often used casually.

In this registry they carry distinct operational meanings.

A requirement labeled `MUST` should be testable.

A prohibition labeled `MUST NOT` should produce a failed validation, hard veto,
or blocked deployment when violated.

A `SHOULD` rule allows a documented exception but does not allow silent
noncompliance.

This distinction prevents a risk limit from being misread as a suggestion.
"""


NORMATIVE_LANGUAGE = {
    "MUST": "Mandatory and machine-enforced.",
    "MUST NOT": "Prohibited and machine-enforced.",
    "SHOULD": "Expected unless a documented exception is approved.",
    "SHOULD NOT": (
        "Normally prohibited unless an exception is approved."
    ),
    "MAY": "Optional behavior.",
    "HARD VETO": "The proposed action cannot continue.",
    "SOFT PENALTY": (
        "The score, confidence, or permissible size is reduced."
    ),
    "WARNING": (
        "The action may continue, but the condition must be logged."
    ),
    "QUARANTINE": (
        "The affected record is isolated and excluded from decision use."
    ),
    "FAIL CLOSED": (
        "Uncertainty results in rejection rather than permissive continuation."
    ),
}


# ==============================================================================
# 4. DIRECTORY MANIFEST
# ==============================================================================

DIRECTORY_MANIFEST_NARRATIVE = """
⬜ WHY THE CONFIGURATION IS SPLIT ACROSS FILES

A single giant configuration file would be easier to create and harder to
govern.

The registry separates concerns so that:

    - Fund identity can change without rewriting risk policy.
    - Risk policy can change without rewriting ontology.
    - Ontology can evolve without silently altering source eligibility.
    - Source parser changes can be reviewed independently.
    - Research, paper, and production environments can share a common base
      while enforcing different restrictions.
    - Each file can have a dedicated schema.
    - Ownership and review responsibility can be assigned by domain.

The separation also supports targeted approval.

A new fund may require research and data review.

A higher options-premium limit should require risk approval.

A new ontology node should require ontology governance.

Those changes should not travel through the same informal approval path.
"""


DIRECTORY_MANIFEST = r"""
config/
├── README.md
├── manifest.json
│
├── fund_universe.json
├── manager_clusters.json
├── source_registry.json
├── strategy_ontology.json
├── model_policy.json
├── governance_policy.json
│
├── profiles/
│   ├── research.json
│   ├── paper.json
│   └── production.json
│
└── schemas/
    ├── manifest.schema.json
    ├── fund_universe.schema.json
    ├── manager_clusters.schema.json
    ├── source_registry.schema.json
    ├── strategy_ontology.schema.json
    ├── model_policy.schema.json
    ├── governance_policy.schema.json
    └── profile.schema.json
"""


# ------------------------------------------------------------------------------
# 4.1 FILE RESPONSIBILITIES
# ------------------------------------------------------------------------------

FILE_RESPONSIBILITIES = {
    "README.md": (
        "Human-readable system specification and runbook."
    ),
    "manifest.json": (
        "Version, hashes, approval state, effective time, and release identity "
        "for the complete bundle."
    ),
    "fund_universe.json": (
        "Stable fund identity, structure, classifications, system roles, "
        "disclosure eligibility, and ontology eligibility."
    ),
    "manager_clusters.json": (
        "Issuer, adviser, portfolio-team, index-methodology, and "
        "corporate-parent relationships."
    ),
    "source_registry.json": (
        "Verified disclosure endpoints, artifact types, parser profiles, "
        "expected publication cadence, and source precedence."
    ),
    "strategy_ontology.json": (
        "Themes, business functions, strategic roles, security mappings, and "
        "mapping provenance."
    ),
    "model_policy.json": (
        "Institutional Adoption Velocity rules, feature definitions, windows, "
        "normalization, penalties, confidence, and stage classification."
    ),
    "governance_policy.json": (
        "Hard limits, vetoes, sizing boundaries, approval requirements, and "
        "kill-switch behavior."
    ),
    "profiles/research.json": (
        "Read-only research configuration. No broker interaction."
    ),
    "profiles/paper.json": (
        "Live or delayed data with simulated execution."
    ),
    "profiles/production.json": (
        "Live production restrictions and approval requirements."
    ),
    "schemas/*.schema.json": (
        "Machine-enforced structural contracts for every configuration file."
    ),
}


CONFIGURATION_OWNERSHIP_MODEL = {
    "fund_universe.json": (
        "Research Governance + Data Governance"
    ),
    "manager_clusters.json": (
        "Research Governance + Legal/Entity Review where applicable"
    ),
    "source_registry.json": (
        "Data Governance"
    ),
    "strategy_ontology.json": (
        "Ontology Governance + Research Governance"
    ),
    "model_policy.json": (
        "Quantitative Research + Model Governance"
    ),
    "governance_policy.json": (
        "Risk Governance"
    ),
    "profiles/production.json": (
        "Engineering Owner + Risk Governance"
    ),
    "manifest.json": (
        "Release Engineering"
    ),
}


# ==============================================================================
# 5. RELEASED BUNDLE IMMUTABILITY
# ==============================================================================

RELEASED_BUNDLE_IMMUTABILITY_NARRATIVE = """
⬜ IMMUTABILITY APPLIES TO RELEASES, NOT IDEAS

The working repository must remain editable.

Research changes.

Sources change.

Fund structures change.

Models improve.

Risk limits are reviewed.

The mistake would be to describe the entire working directory as immutable.

Instead, immutability begins at release.

Once a bundle is approved and used for a decision, that exact bundle must
remain reconstructable.

If a threshold changes from 0.70 to 0.75, the old decision must still point to
the bundle that used 0.70.

If a fund's role changes, the previous role must remain historically visible.

If an ontology mapping is corrected, the correction must not rewrite the
classification that governed an earlier trade.

A released bundle is therefore treated as a historical object.

New information produces a new release.
"""


RELEASED_BUNDLE_IMMUTABILITY = """
The working `config/` directory may be edited through the approved development
process.

A released configuration bundle is immutable.
"""


RELEASE_REQUIREMENTS = (
    "A semantic version.",
    "A schema version.",
    "An effective timestamp.",
    "A source-control commit identifier.",
    "A SHA-256 hash for every normative file.",
    "An approval state.",
    "The identity of each required approver.",
    "A release status.",
    "A rollback target.",
)


RUNTIME_CONFIGURATION_POLICY = """
Runtime services MUST receive a read-only configuration snapshot.
"""


RUNTIME_AGENT_PROHIBITIONS = (
    "Edit configuration files.",
    "Write new ontology mappings directly.",
    "Change risk limits.",
    "Change model weights.",
    "Change source-verification status.",
    "Alter fund eligibility.",
    "Replace the active environment profile.",
)


CONFIGURATION_CHANGE_POLICY = """
Any runtime request to change configuration MUST be converted into a formal
change proposal.
"""


CONFIGURATION_RELEASE_LIFECYCLE = (
    "draft",
    "review",
    "release_candidate",
    "approved",
    "signed",
    "deployed",
    "superseded",
    "rolled_back",
    "retired",
)


# ==============================================================================
# 6. CONFIGURATION LOADER CONTRACT
# ==============================================================================

CONFIGURATION_LOADER_NARRATIVE = """
⬜ WHY DIRECT JSON ACCESS IS PROHIBITED

If every module reads JSON independently, every module can interpret the
registry differently.

One module may:

    - Ignore the manifest.
    - Skip hash verification.
    - Apply a default when a field is missing.
    - Load a newer file than another module.
    - Apply a production override incorrectly.
    - Fail to enforce an invariant.
    - Continue after a partial parsing error.

That creates fragmented truth.

The loader exists to produce one frozen, validated view of the system.

Every downstream component should receive the same configuration snapshot.

The snapshot should have:

    - A bundle version.
    - A bundle hash.
    - A schema version.
    - An environment profile.
    - An effective time.
    - Resolved references.
    - Validated invariants.
    - Read-only behavior.

Once a decision begins, its configuration snapshot should not mutate.
"""


CONFIGURATION_LOADER_CONTRACT = """
All downstream modules MUST access configuration through a single validated
loader.

Recommended entry point:

    src/config/load_registry.py

Downstream modules MUST NOT read JSON files directly.
"""


CONFIGURATION_LOADER_STEPS = (
    "Load `manifest.json`.",
    "Verify the bundle version and effective time.",
    "Verify every declared file hash.",
    "Validate every file against its JSON Schema.",
    "Resolve all cross-file references.",
    "Enforce cross-file invariants.",
    "Apply the active environment profile.",
    "Confirm that profile overrides only tighten permitted behavior.",
    "Freeze the resolved configuration snapshot.",
    "Return a read-only `ConfigSnapshot`.",
    "Record the snapshot hash in every decision and execution audit record.",
)


class ConfigSnapshot:
    """
    Pseudo-class representing the immutable, fully resolved registry state.

    The production implementation may use a frozen dataclass, immutable model,
    or another read-only structure.
    """

    def __init__(
        self,
        bundle_version,
        bundle_hash,
        schema_version,
        profile,
        funds,
        sources,
        manager_clusters,
        ontology,
        model_policy,
        governance_policy,
        effective_at,
    ):
        self.bundle_version = bundle_version
        self.bundle_hash = bundle_hash
        self.schema_version = schema_version
        self.profile = profile
        self.funds = funds
        self.sources = sources
        self.manager_clusters = manager_clusters
        self.ontology = ontology
        self.model_policy = model_policy
        self.governance_policy = governance_policy
        self.effective_at = effective_at


def load_registry(
    config_path: str = "config/",
    profile: str = "production",
    as_of: str = "2026-08-16T13:25:00Z",
):
    """
    Illustrative interface only.

    The production implementation MUST execute the complete validated loader
    contract before returning a frozen configuration snapshot.
    """

    return ConfigSnapshot(
        bundle_version="2.0.0-rc.1",
        bundle_hash="sha256:GENERATED_HASH",
        schema_version="2.0.0",
        profile=profile,
        funds="resolved_fund_registry",
        sources="resolved_source_registry",
        manager_clusters="resolved_manager_clusters",
        ontology="resolved_strategy_ontology",
        model_policy="resolved_model_policy",
        governance_policy="resolved_governance_policy",
        effective_at=as_of,
    )


CONFIG_SNAPSHOT_FIELDS = (
    "snapshot.bundle_version",
    "snapshot.bundle_hash",
    "snapshot.schema_version",
    "snapshot.profile",
    "snapshot.funds",
    "snapshot.sources",
    "snapshot.manager_clusters",
    "snapshot.ontology",
    "snapshot.model_policy",
    "snapshot.governance_policy",
    "snapshot.effective_at",
)


LOADER_FAILURE_BEHAVIOR = {
    "research": (
        "May return a structured validation report, but MUST label the snapshot "
        "invalid and prohibit production use."
    ),
    "paper": (
        "MUST block simulated order generation when a critical invariant fails."
    ),
    "production": (
        "MUST abort startup or activate the applicable kill switch."
    ),
}


# ==============================================================================
# 7. FUND UNIVERSE
# ==============================================================================

# ------------------------------------------------------------------------------
# 7.1 PURPOSE
# ------------------------------------------------------------------------------

FUND_UNIVERSE_NARRATIVE = """
⬜ THE FUND UNIVERSE IS A RESEARCH INSTRUMENT

The fund universe is not merely a list of tradable ETFs.

Each registered fund may serve a different analytical purpose.

Some funds reveal discretionary strategy.

Some reveal rules-based benchmark adoption.

Some provide evidence that a theme is diffusing into adjacent categories.

Some act only as broad beta controls.

Some are useful execution vehicles but poor inference sources.

Some are useful hedges.

Some should be tracked for research but excluded from production.

The registry therefore separates:

    FUND TYPE
        What the fund structurally is.

    SYSTEM ROLE
        How EDGE-TF is permitted to use it.

    ELIGIBILITY
        Whether the fund currently satisfies the requirements for that role.

This prevents the system from making a common category error:

Using every ETF that can be traded as if it also contains useful information
about independent institutional intent.
"""


FUND_UNIVERSE_PURPOSE = """
`fund_universe.json` defines the registered ETF universe available to EDGE-TF.

The initial target universe contains 80 institutional multi-asset ETFs.

The exact active count MUST be declared in `manifest.json`.

A fund may be registered without being eligible for every system role.
"""


REGISTRATION_DOES_NOT_AUTOMATICALLY_MEAN = (
    "Signal eligibility.",
    "Trade eligibility.",
    "Options eligibility.",
    "Hedge eligibility.",
    "Control eligibility.",
    "Production eligibility.",
)


ROLE_SPECIFIC_ELIGIBILITY = True


# ------------------------------------------------------------------------------
# 7.2 FUND TYPE AND SYSTEM ROLE ARE SEPARATE
# ------------------------------------------------------------------------------

FUND_TYPE_AND_ROLE_NARRATIVE = """
⬜ EXAMPLE: ONE FUND, MULTIPLE USES

A transparent active thematic ETF might simultaneously serve as:

    - A signal source.
    - A theme-confirmation source.
    - An implementation candidate.

A broad index ETF might serve as:

    - A beta control.
    - A benchmark.
    - A hedge candidate.
    - A trade vehicle.

A leveraged ETF might serve as:

    - A short-horizon implementation candidate.

But it should usually be:

    - Excluded from inference.

Its daily reset mechanics may create portfolio behavior that is mechanically
required rather than strategically informative.

The use of multiple roles makes the registry more expressive than a single
classification field.
"""


FUND_TYPE_AND_ROLE_POLICY = """
A fund’s structural type describes what the fund is.

A system role describes how EDGE-TF may use it.

These MUST be stored separately.
"""


FUND_TYPES = (
    "active_thematic",
    "rules_based_thematic",
    "specialist_adjacency",
    "active_broad",
    "broad_passive",
    "leveraged_index",
    "inverse_index",
    "fixed_income",
    "commodity",
    "currency",
    "multi_asset",
    "option_overlay",
    "buffered_outcome",
    "other",
)


SYSTEM_ROLES = (
    "signal_source",
    "theme_confirmation",
    "adjacency_detection",
    "benchmark_control",
    "beta_control",
    "macro_control",
    "implementation_candidate",
    "hedge_candidate",
    "options_validation",
    "excluded_from_inference",
    "research_only",
)


MULTI_ROLE_POLICY = """
A fund MAY have multiple system roles.
"""


ACTIVE_THEMATIC_ROLE_EXAMPLE = {
    "fund_type": "active_thematic",
    "system_roles": [
        "signal_source",
        "theme_confirmation",
        "implementation_candidate",
    ],
}


LEVERAGED_ETF_ROLE_EXAMPLE = {
    "fund_type": "leveraged_index",
    "system_roles": [
        "implementation_candidate",
        "excluded_from_inference",
    ],
}


LEVERAGED_ETF_ROLE_RATIONALE = """
This permits the instrument to be evaluated as a trade vehicle without treating
its daily rebalancing as evidence of discretionary institutional strategy.
"""


# ------------------------------------------------------------------------------
# 7.3 MANDATORY FUND ELIGIBILITY GATES
# ------------------------------------------------------------------------------

FUND_ELIGIBILITY_NARRATIVE = """
⬜ REGISTRATION IS NOT ELIGIBILITY

A fund can remain in the registry while temporarily becoming unusable.

Examples:

    - The issuer changes its file format.
    - The disclosure arrives late.
    - A source begins publishing a tracking basket instead of full holdings.
    - A merger creates unresolved identifier history.
    - Options liquidity falls below policy.
    - The ontology mapping becomes stale.
    - The fund liquidates.
    - The fund changes its investment mandate.
    - A leveraged product remains tradable but becomes unsuitable for the
      current intended horizon.

Removing the fund entirely would destroy useful historical context.

Instead, the record remains registered while individual eligibility flags
change.

This supports both historical continuity and current safety.
"""


FUND_ELIGIBILITY_POLICY = """
A fund MAY be admitted to the registry while failing one or more operational
eligibility gates.
"""


RULE_01_DISCLOSURE_ELIGIBILITY = {
    "rule_id": "RULE_01",
    "name": "DISCLOSURE_ELIGIBILITY",
    "requirement": (
        "A signal-generating fund MUST publish verified portfolio information "
        "at a deterministic cadence before the applicable decision cutoff."
    ),
    "regulatory_basis_values": (
        "rule_6c_11",
        "exemptive_order",
        "exchange_requirement",
        "issuer_voluntary",
        "supplemental_regulatory_filing",
        "other_verified_basis",
    ),
    "constraints": (
        "Rule 6c-11 status MUST NOT be treated as the sole eligibility test.",
        "The system cares about the verified substance, completeness, timing, "
        "and reproducibility of the disclosure.",
    ),
}


RULE_01_EXPLANATION = """
⬜ WHY DISCLOSURE ELIGIBILITY IS NOT THE SAME AS RULE 6c-11 STATUS

The engine requires a usable and verified disclosure.

A regulatory label alone does not prove that:

    - The file represents complete holdings.
    - The file arrived before the decision cutoff.
    - The file is consistently published.
    - The source format remains stable.
    - The source is suitable for point-in-time replay.
    - The artifact can be correctly distinguished from a basket or proxy.

Regulatory basis is recorded because it matters.

Operational eligibility is separately verified because the software must act on
the actual artifact, not on an assumption about the artifact.
"""


RULE_02_ARTIFACT_VERIFICATION = {
    "rule_id": "RULE_02",
    "name": "ARTIFACT_VERIFICATION",
    "artifact_types": (
        "full_holdings",
        "portfolio_holdings_file",
        "portfolio_composition_file",
        "creation_basket",
        "redemption_basket",
        "tracking_basket",
        "proxy_portfolio",
        "supplemental_filing",
        "unknown",
    ),
    "requirements": (
        "The system MUST distinguish among the permitted artifact types.",
        "A creation basket, redemption basket, tracking basket, proxy "
        "portfolio, or other substitute artifact MUST NOT be treated as "
        "complete fund holdings unless independently verified as such.",
        "Unknown artifact types MUST fail closed.",
    ),
}


RULE_02_EXPLANATION = """
⬜ WHY ARTIFACT TYPE MATTERS

Different ETF files answer different questions.

A full holdings file may describe the complete portfolio.

A creation basket may describe assets used for a creation transaction.

A redemption basket may describe assets used for redemption.

A tracking basket or proxy portfolio may be designed to help the market price
the ETF without revealing the entire portfolio.

Those files can still be useful.

They cannot be treated as interchangeable.

Misclassifying a basket as complete holdings could create false:

    - Initiations.
    - Exits.
    - Share-count changes.
    - Concentration measures.
    - Theme-purity calculations.
    - Manager-intent inferences.

Artifact verification is therefore a first-order control, not a metadata detail.
"""


RULE_03_CLUSTER_RESOLUTION = {
    "rule_id": "RULE_03",
    "name": "CLUSTER_RESOLUTION",
    "required_clusters": (
        "Issuer cluster.",
        "Adviser cluster.",
        "Subadviser cluster.",
        "Portfolio-management-team cluster.",
        "Index-provider cluster.",
        "Index-methodology cluster.",
        "Ultimate corporate-parent cluster.",
    ),
    "requirements": (
        "Every signal-generating fund MUST map to the applicable clusters.",
        "Manager independence MUST be calculated from relationships among "
        "funds.",
        "Manager independence MUST NOT be stored as a fixed scalar property "
        "of a single fund.",
    ),
}


RULE_04_ONTOLOGY_RELEVANCE = {
    "rule_id": "RULE_04",
    "name": "ONTOLOGY_RELEVANCE",
    "requirement": (
        "Every signal-generating fund MUST map to at least one valid ontology "
        "theme or business function."
    ),
    "separate_measurements": (
        "Mandate relevance.",
        "Observed holdings purity.",
        "Theme density.",
        "Strategic breadth.",
        "Unmapped exposure.",
    ),
    "constraint": (
        "A fund’s prospectus language does not, by itself, establish current "
        "holdings purity."
    ),
}


RULE_05_ROLE_SPECIFIC_LIQUIDITY = {
    "rule_id": "RULE_05",
    "name": "ROLE_SPECIFIC_LIQUIDITY",
    "requirement": (
        "Implementation and hedge vehicles MUST pass the liquidity policy "
        "assigned to their role."
    ),
    "liquidity_dimensions": (
        "Secondary-market dollar volume.",
        "Median bid-ask spread.",
        "Quoted depth.",
        "Estimated market impact.",
        "Fund assets.",
        "Creation-unit characteristics.",
        "Underlying basket liquidity.",
        "Premium and discount behavior.",
        "Options volume.",
        "Options open interest.",
        "Strike density.",
        "LEAP availability.",
        "Options bid-ask spreads.",
        "Estimated contract slippage.",
    ),
    "storage_policy": (
        "Live liquidity values belong in the runtime feature store, not in the "
        "static fund registry."
    ),
}


RULE_05_EXPLANATION = """
⬜ LIQUIDITY DEPENDS ON THE INTENDED ACTION

A fund may be liquid enough to observe but not liquid enough to trade at the
desired size.

An ETF may have adequate cash-market liquidity but inadequate options
liquidity.

A fund may be suitable for a small paper-trading test but not for a production
position.

A hedge vehicle may require greater immediacy than a research candidate.

Liquidity policy is therefore assigned by role.

The registry stores the policy profile.

The runtime feature store supplies the current measurements.
"""


RULE_06_POINT_IN_TIME_INTEGRITY = {
    "rule_id": "RULE_06",
    "name": "POINT_IN_TIME_INTEGRITY",
    "requirements": (
        "A decision MUST use only information that was available before its "
        "recorded decision cutoff.",
        "Backfilled, corrected, or revised data MUST NOT silently overwrite a "
        "historical record.",
    ),
}


RULE_07_DATA_QUALITY = {
    "rule_id": "RULE_07",
    "name": "DATA_QUALITY",
    "fail_closed_conditions": (
        "Missing.",
        "Stale.",
        "Malformed.",
        "Internally inconsistent.",
        "Unverified.",
        "Partially parsed.",
        "Subject to an unresolved corporate action.",
        "Published after the decision cutoff.",
        "From an unrecognized artifact type.",
    ),
}


RULE_08_PROVENANCE = {
    "rule_id": "RULE_08",
    "name": "PROVENANCE",
    "required_fields": (
        "Source identifier.",
        "Source URL or connector reference.",
        "Raw-file hash.",
        "Raw-file storage location.",
        "Portfolio effective date.",
        "Publication time.",
        "First observed time.",
        "Ingestion time.",
        "Parser version.",
        "Configuration bundle version.",
        "Revision status.",
    ),
}


# ------------------------------------------------------------------------------
# 7.4 ASSET AND EXPOSURE METADATA
# ------------------------------------------------------------------------------

ASSET_METADATA_NARRATIVE = """
⬜ WHY STRUCTURAL METADATA MATTERS

Two funds can hold similar securities while producing very different economic
exposures.

Differences may arise from:

    - Long versus inverse exposure.
    - Daily leverage.
    - Currency hedging.
    - Derivative overlays.
    - Covered-call strategies.
    - Buffer structures.
    - Duration exposure.
    - Commodity futures.
    - Multi-asset allocation.
    - Regional concentration.

The system must understand what the wrapper does before treating its holdings
or price behavior as comparable evidence.
"""


RECOMMENDED_FUND_METADATA = (
    "asset_class",
    "region",
    "currency",
    "exposure_direction",
    "leverage_factor",
    "derivative_usage",
    "distribution_policy",
    "benchmark_type",
    "management_style",
)


ASSET_CLASS_VALUES = (
    "equity",
    "fixed_income",
    "commodity",
    "currency",
    "multi_asset",
    "alternatives",
)


EXPOSURE_DIRECTION_VALUES = (
    "long",
    "short",
    "long_short",
    "leveraged_long",
    "leveraged_short",
    "buffered",
    "option_overlay",
)


# ------------------------------------------------------------------------------
# 7.5 STABLE IDENTITY
# ------------------------------------------------------------------------------

STABLE_IDENTITY_NARRATIVE = """
⬜ TICKERS CHANGE; IDENTITY MUST NOT

A ticker is designed for market use.

It is not a durable database key.

A fund may:

    - Change ticker.
    - Change exchange.
    - Merge into another fund.
    - Convert from another structure.
    - Liquidate.
    - Relaunch under similar branding.
    - Change adviser.
    - Change benchmark.
    - Change mandate.

Historical analysis must distinguish continuity from coincidence.

A stable internal `fund_id` allows the system to preserve the legal and
economic history while separately recording changing listings and attributes.
"""


STABLE_IDENTITY_POLICY = """
Tickers are aliases, not permanent identities.

The system MUST assign every fund a stable internal `fund_id`.

Do not use the current ticker as the permanent identifier.
"""


RECOMMENDED_FUND_ID_FORMATS = (
    "fund_us_000001",
    "fund_us_000002",
    "fund_us_000003",
)


IDENTITY_HISTORY_REQUIREMENTS = (
    "Ticker history MUST be effective-dated.",
    "Fund mergers MUST be represented explicitly.",
    "Fund liquidations MUST be represented explicitly.",
    "Fund conversions MUST be represented explicitly.",
    "Fund relaunches MUST be represented explicitly.",
    "Exchange changes MUST be represented explicitly.",
    "Ticker changes MUST be represented explicitly.",
)


# ------------------------------------------------------------------------------
# 7.6 CANONICAL FUND RECORD
# ------------------------------------------------------------------------------

CANONICAL_FUND_RECORD_NARRATIVE = """
⬜ HOW TO READ THE CANONICAL FUND RECORD

The canonical fund record contains stable and reviewed declarations.

It does not attempt to contain every fact about the fund.

The record answers:

    IDENTITY
        What fund is this?

    LISTING
        How is it currently traded?

    ENTITIES
        Who issues, advises, manages, or benchmarks it?

    STRUCTURE
        What kind of fund is it?

    SYSTEM ROLES
        How may EDGE-TF use it?

    ELIGIBILITY
        Which roles are currently allowed?

    DISCLOSURE
        What artifact is expected, from which verified source?

    ONTOLOGY
        Which themes and business functions are relevant to the mandate?

    MANAGEMENT
        Is the process discretionary, systematic, or scheduled?

    LIQUIDITY POLICY
        Which runtime liquidity tests must it pass?

    PROVENANCE
        Who reviewed the declaration and from what documents?

The record intentionally excludes current market observations.
"""


CANONICAL_FUND_RECORD = {
    "schema_version": "2.0.0",
    "record_version": 1,

    "fund_id": "fund_us_000042",
    "status": "active",

    "effective_from": "2026-08-16T00:00:00Z",
    "effective_to": None,

    "identity": {
        "legal_name": "Full ETF Name",
        "domicile": "US",
        "legal_structure": "open_end_management_company",
        "sec_series_id": None,
        "sec_class_contract_id": None,
        "lei": None,
    },

    "listings": [
        {
            "ticker": "TICKER",
            "exchange_mic": "ARCX",
            "currency": "USD",
            "valid_from": "2024-01-01T00:00:00Z",
            "valid_to": None,
        }
    ],

    "entities": {
        "issuer_id": "issuer_001",
        "adviser_id": "adviser_001",
        "subadviser_id": None,
        "portfolio_team_cluster_id": "pm_cluster_001",
        "index_provider_id": None,
        "index_methodology_cluster_id": None,
        "ultimate_parent_cluster_id": "parent_cluster_001",
    },

    "asset_class": "equity",
    "fund_type": "active_thematic",
    "exposure_direction": "long",
    "leverage_factor": 1.0,

    "system_roles": [
        "signal_source",
        "theme_confirmation",
        "implementation_candidate",
    ],

    "eligibility": {
        "signal_eligible": True,
        "implementation_eligible": True,
        "control_eligible": False,
        "hedge_eligible": False,
        "options_eligible": True,
    },

    "disclosure": {
        "regime": "full_holdings_daily",
        "regulatory_basis": "rule_6c_11",
        "artifact_type": "full_holdings",
        "source_id": "source_001",
        "expected_cadence": "business_daily",
        "expected_availability": "before_primary_market_open",
        "full_holdings_verified": True,
        "last_verified_at": "2026-08-16T00:00:00Z",
    },

    "ontology": {
        "primary_theme_id": "theme_enterprise_ai",
        "eligible_functions": [
            {
                "function_id": "function_decision_intelligence",
                "mandate_relevance": 0.95,
            },
            {
                "function_id": "function_data_infrastructure",
                "mandate_relevance": 0.75,
            },
        ],
        "mapping_methodology_version": "ontology_mapping_v1",
    },

    "management": {
        "style": "discretionary_active",
        "scheduled_rebalance_frequency": None,
        "scheduled_reconstitution_frequency": None,
    },

    "benchmark": {
        "benchmark_id": None,
        "benchmark_name": None,
    },

    "liquidity_policy_profile": "options_execution",

    "provenance": {
        "created_at": "2026-08-16T00:00:00Z",
        "reviewed_at": "2026-08-16T00:00:00Z",
        "reviewed_by": "research_governance",
        "source_documents": [
            "prospectus",
            "statement_of_additional_information",
            "issuer_fund_page",
        ],
    },
}


# ------------------------------------------------------------------------------
# 7.7 PROHIBITED STATIC FIELDS
# ------------------------------------------------------------------------------

STATIC_VERSUS_DYNAMIC_NARRATIVE = """
⬜ WHY LIVE FEATURES DO NOT BELONG IN THE FUND REGISTRY

A fund registry is expected to change slowly.

Market features can change every minute.

Combining them would create several problems:

    - The registry would need constant rewriting.
    - Every market update could create a new configuration release.
    - Historical reconstruction would become difficult.
    - A stale liquidity score could appear authoritative.
    - Model output could be mistaken for human-approved policy.
    - Changes in market state could alter the bundle hash continuously.

The registry should define how a feature is evaluated.

The feature store should contain the time-stamped value.
"""


PROHIBITED_STATIC_FIELDS = (
    "Current liquidity score.",
    "Current concentration score.",
    "Current turnover score.",
    "Current disclosure reliability score.",
    "Current manager-independence score.",
    "Current Institutional Adoption Velocity.",
    "Current crowding score.",
    "Current theme purity.",
    "Current bid-ask spread.",
    "Current assets under management.",
    "Current options open interest.",
)


PROHIBITED_STATIC_FIELD_POLICY = """
These are time-varying observations or derived features.

They belong in the data warehouse or feature store with timestamps and
calculation versions.
"""


# ==============================================================================
# 8. SOURCE REGISTRY AND INGESTION POLICY
# ==============================================================================

# ------------------------------------------------------------------------------
# 8.1 PURPOSE
# ------------------------------------------------------------------------------

SOURCE_REGISTRY_NARRATIVE = """
⬜ THE SOURCE REGISTRY IS THE BEGINNING OF THE EVIDENCE CHAIN

A model cannot become more reliable than its evidence chain.

The source registry records what the system expects before the source is
collected.

That expectation matters because the system must detect change.

If an issuer normally publishes:

    - A CSV.
    - At a specific endpoint.
    - With a specific header.
    - Before a specific time.
    - Representing full holdings.

Then a sudden HTML page, missing column, late file, or tracking basket should
not be accepted silently.

The source registry turns an external website into a governed input contract.
"""


SOURCE_REGISTRY_PURPOSE = """
`source_registry.json` defines the approved sources from which ETF disclosures
may be collected.
"""


SOURCE_RECORD_REQUIREMENTS = (
    "The fund.",
    "The source owner.",
    "The expected artifact type.",
    "The endpoint or connector.",
    "The expected file format.",
    "The expected cadence.",
    "The publication timezone.",
    "The expected availability window.",
    "The parser profile.",
    "The source-precedence rank.",
    "Verification status.",
    "Known anomalies.",
    "Failover behavior.",
)


# ------------------------------------------------------------------------------
# 8.2 CANONICAL SOURCE RECORD
# ------------------------------------------------------------------------------

CANONICAL_SOURCE_RECORD = {
    "schema_version": "2.0.0",
    "source_id": "source_001",
    "fund_id": "fund_us_000042",

    "source_owner": "Issuer Name",
    "source_type": "issuer_primary",

    "artifact_type": "full_holdings",
    "format": "csv",
    "endpoint": "https://issuer.example/fund/holdings.csv",

    "publication": {
        "expected_cadence": "business_daily",
        "timezone": "America/New_York",
        "expected_by_local_time": "08:30:00",
        "market_holiday_behavior": "no_file_expected",
    },

    "parser": {
        "profile_id": "issuer_csv_v3",
        "parser_version": "3.1.0",
        "header_signature": [
            "Ticker",
            "CUSIP",
            "Shares",
            "Market Value",
            "Weight",
        ],
    },

    "verification": {
        "status": "verified",
        "verified_at": "2026-08-16T00:00:00Z",
        "verified_by": "data_governance",
        "full_holdings_confirmed": True,
    },

    "precedence": 1,
    "fallback_source_id": None,
    "known_issues": [],
}


# ------------------------------------------------------------------------------
# 8.3 SOURCE PRECEDENCE
# ------------------------------------------------------------------------------

SOURCE_PRECEDENCE_NARRATIVE = """
⬜ WHY A FALLBACK SOURCE CANNOT SILENTLY BECOME THE PRIMARY SOURCE

Different sources can disagree.

They may use:

    - Different effective dates.
    - Different identifier conventions.
    - Different rounding.
    - Different treatment of derivatives.
    - Different publication times.
    - Different revisions.

A fallback is useful during an outage.

It is not permission to erase the distinction between sources.

The system should record:

    - Which source failed.
    - Which fallback was used.
    - Why the fallback was eligible.
    - Whether confidence was reduced.
    - Which decisions depended on the fallback.

Source substitution must be visible in the audit trail.
"""


SOURCE_PRECEDENCE = (
    "Verified issuer primary source.",
    "Verified adviser or administrator source.",
    "Verified exchange or regulatory source.",
    "Verified licensed data provider.",
    "Secondary public source.",
    "Unverified source.",
)


SOURCE_PRECEDENCE_POLICY = """
Unverified sources MUST NOT support production trade decisions.

A secondary source MAY be used to detect a discrepancy but MUST NOT silently
replace a higher-precedence source.
"""


# ------------------------------------------------------------------------------
# 8.4 RAW FILE PRESERVATION
# ------------------------------------------------------------------------------

RAW_FILE_PRESERVATION_NARRATIVE = """
⬜ NORMALIZED DATA IS NOT ENOUGH

A normalized row tells the system what the parser believed.

The raw artifact shows what the issuer actually published.

Both are required.

Without the raw file, the system cannot later determine whether:

    - The source was malformed.
    - The parser misinterpreted a column.
    - A header changed.
    - A decimal or percentage was scaled incorrectly.
    - An issuer corrected the file.
    - A security identifier was ambiguous.
    - A row was omitted.

Raw preservation allows the normalized result to be challenged.
"""


RAW_FILE_POLICY = """
Every downloaded source artifact MUST be stored before transformation.
"""


RAW_FILE_REQUIREMENTS = (
    "Immutable.",
    "Timestamped.",
    "Content-hashed.",
    "Linked to its source record.",
    "Linked to the parser version.",
    "Linked to the resulting normalized records.",
)


CORRECTED_FILE_POLICY = """
Corrected issuer files MUST be stored as new revisions.

No correction may erase the originally observed file.
"""


# ==============================================================================
# 9. MANAGER CLUSTERS AND INDEPENDENCE
# ==============================================================================

# ------------------------------------------------------------------------------
# 9.1 PURPOSE
# ------------------------------------------------------------------------------

MANAGER_INDEPENDENCE_NARRATIVE = """
⬜ THREE FUNDS DO NOT NECESSARILY EQUAL THREE INDEPENDENT VOTES

Cross-manager overlap is one of the most important components of the EDGE-TF
method.

It is also easy to overstate.

Three funds may hold the same company because:

    - The same portfolio team manages all three.
    - The same adviser applies one research process across products.
    - The same index methodology requires the position.
    - One fund is a clone or feeder.
    - A common corporate parent coordinates strategy.
    - The same rebalance event affected all three.

Counting those funds as three fully independent confirmations would inflate
the signal.

Manager clustering converts raw fund count into evidence quality.
"""


MANAGER_CLUSTER_PURPOSE = """
Cross-manager confirmation is meaningful only when the managers are genuinely
independent.

Different ticker symbols do not establish independence.

Different issuers do not necessarily establish independence.
"""


SHARED_RELATIONSHIP_TYPES = (
    "An adviser.",
    "A subadviser.",
    "A portfolio-management team.",
    "An index provider.",
    "An index methodology.",
    "A corporate parent.",
    "A research process.",
    "A common model portfolio.",
    "A common rebalance event.",
)


MANAGER_CLUSTER_FILE_PURPOSE = """
`manager_clusters.json` defines these relationships.
"""


# ------------------------------------------------------------------------------
# 9.2 REQUIRED CLUSTER TYPES
# ------------------------------------------------------------------------------

REQUIRED_CLUSTER_TYPES = (
    "issuer_cluster",
    "adviser_cluster",
    "subadviser_cluster",
    "portfolio_team_cluster",
    "index_provider_cluster",
    "index_methodology_cluster",
    "ultimate_parent_cluster",
    "research_process_cluster",
)


# ------------------------------------------------------------------------------
# 9.3 INDEPENDENCE IS PAIRWISE
# ------------------------------------------------------------------------------

PAIRWISE_INDEPENDENCE_NARRATIVE = """
⬜ WHY INDEPENDENCE IS A RELATIONSHIP

A fund cannot be 95 percent independent in isolation.

It can only be more or less independent relative to another fund or group.

For example:

    Fund A and Fund B:
        Same portfolio team.
        Independence contribution may be near zero.

    Fund A and Fund C:
        Different advisers but same index methodology.
        Independence may be partial.

    Fund A and Fund D:
        Different corporate groups, teams, mandates, and methodologies.
        Independence may be high.

The actual penalty should be produced from declared relationships and the
active model policy.

It should not be entered as an unexplained score in a fund record.
"""


PAIRWISE_INDEPENDENCE_POLICY = """
Manager independence MUST be calculated when comparing two or more funds.

It MUST NOT be stored as a fixed scalar value on a single fund record.
"""


INVALID_MANAGER_INDEPENDENCE_EXAMPLE = {
    "manager_independence": 0.95,
}


INDEPENDENCE_COMPARISON_FACTORS = (
    "Shared portfolio team.",
    "Shared adviser.",
    "Shared subadviser.",
    "Shared ultimate parent.",
    "Shared index methodology.",
    "Shared rebalance schedule.",
    "Shared disclosed model.",
    "Shared benchmark.",
    "Known feeder or clone relationships.",
)


INDEPENDENCE_PENALTY_LOCATION = """
The exact penalty matrix belongs in `model_policy.json`.
"""


# ------------------------------------------------------------------------------
# 9.4 CANONICAL CLUSTER RECORD
# ------------------------------------------------------------------------------

CANONICAL_CLUSTER_RECORD = {
    "schema_version": "2.0.0",
    "cluster_id": "pm_cluster_001",
    "cluster_type": "portfolio_team_cluster",
    "name": "Portfolio Team A",
    "member_entity_ids": [
        "adviser_001",
        "fund_us_000042",
        "fund_us_000057",
    ],
    "effective_from": "2025-01-01T00:00:00Z",
    "effective_to": None,
    "provenance": {
        "reviewed_at": "2026-08-16T00:00:00Z",
        "reviewed_by": "research_governance",
    },
}


# ==============================================================================
# 10. STRATEGY-FIRST ONTOLOGY
# ==============================================================================

# ------------------------------------------------------------------------------
# 10.1 PURPOSE
# ------------------------------------------------------------------------------

STRATEGY_FIRST_NARRATIVE = """
⬜ WHY THE SYSTEM STARTS WITH BUSINESS FUNCTION

A sector label is often too broad to explain why a manager owns a company.

"Technology" may contain companies that perform entirely different jobs.

"Software" may include:

    - Enterprise decision systems.
    - Workflow automation.
    - Cybersecurity.
    - Data resilience.
    - Advertising monetization.
    - Developer infrastructure.
    - Industrial operations.
    - Cloud infrastructure.

Those companies may share a sector while expressing different strategies.

The Strategy-First Ontology asks:

    What function does this company perform inside the investment thesis?

The answer helps the system:

    - Compare like with like.
    - Detect strategic diffusion.
    - Build purer implementation baskets.
    - Avoid broad ticker screens.
    - Explain why a fund holds a security.
    - Separate core exposure from incidental exposure.
"""


STRATEGY_ONTOLOGY_PURPOSE = """
`strategy_ontology.json` defines the language through which EDGE-TF interprets
portfolio behavior.

The system does not treat the ticker as the primary unit of strategy.
"""


ANALYTICAL_HIERARCHY = (
    "Market Regime",
    "Strategic Theme",
    "Business Function",
    "Functional Role",
    "Company",
    "Security",
    "Trade Vehicle",
)


SECTOR_LABEL_POLICY = """
Traditional sector labels may be retained as metadata, but they MUST NOT
replace the Strategy-First Ontology.
"""


# ------------------------------------------------------------------------------
# 10.2 ONTOLOGY OBJECTIVES
# ------------------------------------------------------------------------------

ONTOLOGY_OBJECTIVE = """
The ontology MUST allow the system to distinguish among companies that may
share a broad sector classification but perform different strategic functions.
"""


ILLUSTRATIVE_BUSINESS_FUNCTIONS = (
    "enterprise_decision_intelligence",
    "enterprise_ai_infrastructure",
    "ai_monetization",
    "ai_native_cybersecurity",
    "data_resilience",
    "industrial_operations_intelligence",
    "workflow_automation",
    "developer_infrastructure",
    "semiconductor_compute",
    "network_interconnect",
    "power_infrastructure",
    "robotics",
    "autonomous_systems",
    "defense_technology",
    "nuclear_energy",
)


# ------------------------------------------------------------------------------
# 10.3 FUNCTIONAL ROLES
# ------------------------------------------------------------------------------

FUNCTIONAL_ROLE_NARRATIVE = """
⬜ THE SAME COMPANY CAN SERVE DIFFERENT ROLES

A company may be:

    - Core to one strategy.
    - An enabler in another.
    - Incidental in a third.

For example, a data platform could be:

    - A core implementation of enterprise decision intelligence.
    - An enabling layer for cybersecurity.
    - A minor incidental position in a broad software ETF.

The mapping therefore needs both:

    - The business function.
    - The role inside the specific strategy.

This improves both inference and trade design.
"""


FUNCTIONAL_ROLES = (
    "core",
    "enabler",
    "infrastructure",
    "application",
    "monetizer",
    "security",
    "data_layer",
    "distribution",
    "hedge",
    "liquidity",
    "incidental",
    "unknown",
)


FUNCTIONAL_ROLE_POLICY = """
A security mapping SHOULD state the role the company performs inside a
strategy.

This allows the system to distinguish a strategy’s core exposure from
incidental portfolio holdings.
"""


# ------------------------------------------------------------------------------
# 10.4 ONTOLOGY NODE REQUIREMENTS
# ------------------------------------------------------------------------------

ONTOLOGY_NODE_REQUIREMENTS = (
    "Stable identifier.",
    "Human-readable label.",
    "Parent identifier.",
    "Description.",
    "Inclusion criteria.",
    "Exclusion criteria.",
    "Effective date.",
    "Version.",
    "Status.",
    "Review provenance.",
)


ONTOLOGY_DRIFT_WARNING = """
🟨 ONTOLOGY DRIFT

Business language changes quickly.

Marketing descriptions change even faster.

The ontology should not automatically adopt every new term used in earnings
calls, investor presentations, or thematic fund names.

A useful ontology node should be:

    - Specific enough to distinguish a business function.
    - Stable enough to support historical analysis.
    - Broad enough to include legitimate peers.
    - Clear enough to define exclusions.
    - Reviewable by a human analyst.
"""


# ------------------------------------------------------------------------------
# 10.5 CANONICAL FUNCTION NODE
# ------------------------------------------------------------------------------

CANONICAL_FUNCTION_NODE = {
    "function_id": "function_industrial_operations_intelligence",
    "label": "Industrial Operations Intelligence",
    "parent_theme_id": "theme_industrial_ai",
    "description": (
        "Platforms that connect physical operations, assets, workers, "
        "telemetry, workflows, and AI-enabled operational analytics."
    ),
    "inclusion_criteria": [
        "Material exposure to physical operations or connected assets",
        "Operational workflow or telemetry platform",
        "AI or analytics applied to operational decision-making",
    ],
    "exclusion_criteria": [
        "Generic enterprise workflow without physical operations exposure",
        "Pure hardware exposure without an operational intelligence layer",
    ],
    "status": "active",
    "effective_from": "2026-08-16T00:00:00Z",
    "effective_to": None,
    "ontology_version": "2.0.0",
}


# ------------------------------------------------------------------------------
# 10.6 CANONICAL SECURITY MAPPING
# ------------------------------------------------------------------------------

CANONICAL_SECURITY_MAPPING = {
    "security_id": "security_us_example",
    "function_id": "function_industrial_operations_intelligence",
    "functional_role": "core",
    "mapping_confidence": 0.92,
    "effective_from": "2026-08-16T00:00:00Z",
    "effective_to": None,
    "methodology_version": "security_mapping_v2",
    "review": {
        "status": "approved",
        "reviewed_by": "ontology_governance",
        "reviewed_at": "2026-08-16T00:00:00Z",
    },
}


# ------------------------------------------------------------------------------
# 10.7 AGENT-PROPOSED ONTOLOGY CHANGES
# ------------------------------------------------------------------------------

AGENT_ONTOLOGY_NARRATIVE = """
🟪 AGENTS MAY DISCOVER; AGENTS MAY NOT SELF-APPROVE

An agent can help identify:

    - A new business model.
    - A company whose revenue mix changed.
    - A stale mapping.
    - A missing peer.
    - A category that is too broad.
    - A category that is too narrow.

That is useful research work.

But an ontology change affects:

    - Historical comparisons.
    - Theme purity.
    - IAV aggregation.
    - Candidate rankings.
    - Portfolio exposure.
    - Trade design.

The proposing agent cannot also be the approving authority.

A proposed mapping remains nonproduction until reviewed and released.
"""


AGENT_ONTOLOGY_PERMISSIONS = (
    "Propose a new ontology node.",
    "Propose a new security mapping.",
    "Propose a mapping-confidence change.",
    "Flag a stale or ambiguous classification.",
    "Generate supporting rationale.",
)


AGENT_ONTOLOGY_PROHIBITIONS = (
    "Activate a new ontology node.",
    "Modify a production mapping.",
    "Retire an ontology node.",
    "Change an approved mapping’s effective date.",
    "Mark their own proposal as approved.",
)


ONTOLOGY_CHANGE_POLICY = """
Ontology changes require human review and a new configuration release.
"""


# ==============================================================================
# 11. MANDATE RELEVANCE AND HOLDINGS PURITY
# ==============================================================================

MANDATE_AND_PURITY_NARRATIVE = """
⬜ WHAT A FUND SAYS VERSUS WHAT A FUND CURRENTLY OWNS

A thematic prospectus may be highly relevant to a business function.

The current portfolio may not be pure.

Reasons include:

    - Cash.
    - Liquidity holdings.
    - Broad mega-cap positions.
    - Temporary hedges.
    - Derivative overlays.
    - Diversification requirements.
    - Position limits.
    - Transition between themes.
    - Manager discretion.
    - Rebalance timing.

Mandate relevance answers:

    Is this fund designed to express the function?

Observed holdings purity answers:

    How much of the current economic exposure actually expresses it?

Both measures matter.

They answer different questions.
"""


# ------------------------------------------------------------------------------
# 11.1 SEPARATE CONCEPTS
# ------------------------------------------------------------------------------

MANDATE_RELEVANCE = """
How strongly a fund’s governing documents and stated strategy map to an
ontology function.
"""


OBSERVED_HOLDINGS_PURITY = """
How much of the fund’s current economic exposure maps to the eligible ontology
function.
"""


MANDATE_AND_PURITY_POLICY = """
A prospectus establishes mandate relevance.

Current holdings establish observed purity.

They are related but not interchangeable.
"""


# ------------------------------------------------------------------------------
# 11.2 PURITY CALCULATION
# ------------------------------------------------------------------------------

PURITY_FORMULA = """
Observed Holdings Purity
=
Mapped Eligible Economic Exposure
÷
Total Eligible Economic Exposure
"""


PURITY_POLICY_REQUIREMENTS = (
    "Whether cash is excluded.",
    "Whether derivatives use notional, delta-adjusted, or another exposure "
    "measure.",
    "Whether short positions reduce net purity or contribute to gross purity.",
    "Whether fund-of-fund positions receive look-through treatment.",
    "How unmapped positions are treated.",
    "How foreign listings and depositary receipts are consolidated.",
    "How duplicate economic exposures are handled.",
    "Whether purity is measured daily or over a rolling window.",
)


PURITY_THRESHOLD_POLICY = """
Thresholds MUST be defined by fund type in `model_policy.json`.

A specialist thematic fund and an active broad fund SHOULD NOT be required to
satisfy the same purity threshold.
"""


PURITY_INTERPRETATION = {
    "high_mandate_high_purity": (
        "Strong strategic source and potentially strong implementation vehicle."
    ),
    "high_mandate_low_purity": (
        "Relevant stated mandate, but current exposure may be diluted or in "
        "transition."
    ),
    "low_mandate_high_purity": (
        "Current holdings align, but the alignment may be temporary or "
        "incidental."
    ),
    "low_mandate_low_purity": (
        "Weak source for the intended strategic inference."
    ),
}


# ==============================================================================
# 12. QUANTITATIVE MODEL POLICY
# ==============================================================================

# ------------------------------------------------------------------------------
# 12.1 PURPOSE
# ------------------------------------------------------------------------------

MODEL_POLICY_NARRATIVE = """
⬜ MODEL POLICY IS NOT GOVERNANCE POLICY

The model estimates evidence strength.

Governance determines what the system is allowed to do.

Those functions must remain separate.

For example:

    - A model may assign a high IAV score.
    - Governance may still prohibit the trade because of liquidity.
    - A model may identify strong adoption.
    - Governance may cap position size because the portfolio is already
      concentrated in the theme.
    - An options model may prefer a long-dated contract.
    - Governance may reject it because the spread is too wide.

Keeping model and governance files separate prevents a model change from
quietly changing the risk constitution.
"""


MODEL_POLICY_PURPOSE = """
`model_policy.json` contains the quantitative rules used to convert normalized
disclosure history into research signals.
"""


MODEL_POLICY_REQUIREMENTS = (
    "Feature definitions.",
    "Lookback windows.",
    "Normalization methods.",
    "Component weights.",
    "Persistence rules.",
    "Manager-independence adjustments.",
    "Mandate-relevance adjustments.",
    "Data-quality adjustments.",
    "Crowding and saturation penalties.",
    "Corporate-action filters.",
    "Confidence-calibration rules.",
    "Adoption-stage thresholds.",
    "Missing-data behavior.",
    "Signal upgrade and downgrade requirements.",
)


MODEL_PARAMETER_LOCATION_POLICY = """
Numeric model values MUST NOT exist only in this README.
"""


# ------------------------------------------------------------------------------
# 12.2 INSTITUTIONAL ADOPTION VELOCITY
# ------------------------------------------------------------------------------

IAV_NARRATIVE = """
⬜ WHAT IAV IS TRYING TO MEASURE

Institutional Adoption Velocity is designed to measure ownership formation.

It does not ask only:

    How much of the company do ETFs own?

It asks:

    How quickly is relevant institutional representation changing?

The framework treats adoption as multidimensional.

A stronger pattern may include:

    - New relevant ETF initiations.
    - More active funds holding the security.
    - Rising aggregate shares.
    - Expansion across related themes.
    - Persistence across disclosure windows.
    - Confirmation by independent managers.
    - Continued room for future allocation.

A weaker or misleading pattern may include:

    - Weight growth caused only by price.
    - Multiple funds controlled by the same team.
    - Passive index inclusion.
    - Corporate-action distortions.
    - Broad sector beta.
    - A mature and saturated ownership state.
    - One aggressive but isolated manager.

IAV is therefore not a raw sum.

It is a scored interpretation of adoption evidence.
"""


IAV_COMPONENTS = {
    "NI": "New ETF Initiations",
    "AO": "Change in Relevant Active ETF Ownership",
    "AS": "Change in Aggregate Shares Held",
    "TP": "Change in Theme Participation",
}


IAV_CORE_FORMULA = """
IAV Core
=
wNI × NI
+
wAO × AO
+
wAS × AS
+
wTP × TP
"""


IAV_QUALITY_ADJUSTMENTS = {
    "P": "Persistence",
    "MI": "Manager Independence",
    "MR": "Mandate Relevance",
    "DQ": "Data Quality",
    "RTG": "Room for Future Allocation",
}


IAV_STRUCTURAL_PENALTIES = {
    "PI": "Passive or Mechanical Inclusion",
    "CA": "Corporate Action Distortion",
    "CR": "Crowding",
    "ST": "Saturation",
    "PD": "Price-Driven Weight Drift",
    "MD": "Manager Dependence",
}


ADJUSTED_IAV_FORMULA = """
Adjusted IAV
=
IAV Core
× Persistence Quality
× Independence Quality
× Mandate Relevance
× Data Quality
× Room-to-Grow Adjustment
− Structural Penalties
"""


IAV_IMPLEMENTATION_POLICY = """
The precise formula, normalization, winsorization, weighting, and clipping rules
belong in `model_policy.json`.
"""


IAV_INTERPRETATION_EXAMPLE = """
⬜ HYPOTHETICAL IAV EXAMPLE

Company Alpha:

    - Already held by 40 relevant ETFs.
    - Top-five holding in several funds.
    - Aggregate shares unchanged.
    - No new theme participation.
    - High crowding.
    - High current ownership.

Company Beta:

    - Previously held by 2 relevant ETFs.
    - Newly initiated by 4 independent active managers.
    - Aggregate shares rising.
    - Expanding from one function-adjacent theme into three.
    - Still a modest portfolio weight.
    - Moderate liquidity and low current crowding.

A conventional top-holdings screen may rank Company Alpha higher.

An ownership-formation model may identify Company Beta as the more interesting
research candidate.

That does not make Company Beta a validated trade.

It makes Company Beta a candidate for deeper validation.
"""


# ------------------------------------------------------------------------------
# 12.3 SHARES BEFORE WEIGHT
# ------------------------------------------------------------------------------

SHARES_BEFORE_WEIGHT_NARRATIVE = """
⬜ WEIGHT IS AN OUTPUT OF MULTIPLE VARIABLES

Portfolio weight is not a pure record of manager choice.

A simplified relationship is:

    weight
    =
    position market value
    ÷
    total portfolio market value

The numerator can rise because:

    - Shares increased.
    - Price increased.
    - A corporate action changed units.

The denominator can change because:

    - The fund received flows.
    - The fund experienced redemptions.
    - Other holdings moved.
    - Cash changed.
    - Derivative values changed.

The system therefore treats weight as useful but insufficient.

Share-count change is often more informative, but it also requires adjustment
for flows, splits, mergers, and other events.
"""


WEIGHT_CHANGE_CAUSES = (
    "The manager bought more shares.",
    "The security’s price appreciated.",
    "Other holdings declined.",
    "The fund experienced flows.",
    "A rebalance occurred.",
    "A corporate action changed units.",
    "Derivative exposure changed.",
    "Cash levels changed.",
)


SHARES_BEFORE_WEIGHT_POLICY = """
Weight change alone MUST NOT be treated as proof of manager accumulation.
"""


REQUIRED_HOLDING_CHANGE_FEATURES = (
    "share_count_delta",
    "weight_delta",
    "market_value_delta",
    "price_contribution",
    "flow_adjusted_share_delta",
    "corporate_action_adjusted_share_delta",
)


PRICE_DRIFT_POLICY = """
A signal based primarily on weight movement without share confirmation MUST
receive a price-drift penalty or fail the applicable evidence threshold.
"""


# ------------------------------------------------------------------------------
# 12.4 OWNERSHIP FORMATION VS. OWNERSHIP CONSENSUS
# ------------------------------------------------------------------------------

OWNERSHIP_STATE_NARRATIVE = """
⬜ GOOD COMPANY DOES NOT ALWAYS MEAN EARLY SIGNAL

The system is not designed to deny the quality of mature market leaders.

It is designed to distinguish two different research questions:

    1. Is this company widely owned?
    2. Is ownership still forming?

A widely owned company may continue to outperform.

But the informational edge from detecting institutional adoption may be lower
once ownership, narrative, and portfolio weight are already mature.

The ownership-formation framework attempts to identify the migration process
before it becomes a static consensus snapshot.
"""


OWNERSHIP_FORMATION = {
    "definition": (
        "Institutional participation is broadening or intensifying."
    ),
    "possible_indicators": (
        "New relevant fund initiations.",
        "Rising aggregate shares.",
        "Increasing manager breadth.",
        "New theme participation.",
        "Persistent additions.",
        "Low or moderate existing crowding.",
    ),
}


OWNERSHIP_CONSENSUS = {
    "definition": (
        "The security is already broadly owned."
    ),
    "possible_indicators": (
        "High fund participation.",
        "High portfolio concentration.",
        "Mature top-holding status.",
        "Low incremental breadth.",
        "Low room for future allocation.",
        "High narrative saturation.",
    ),
}


OWNERSHIP_STATE_POLICY = """
A company may be an excellent business while producing little
ownership-formation edge.

The model is designed to detect changing adoption, not merely large ownership.
"""


# ------------------------------------------------------------------------------
# 12.5 INSTITUTIONAL ADOPTION CURVE
# ------------------------------------------------------------------------------

ADOPTION_CURVE_NARRATIVE = """
⬜ THE ADOPTION CURVE IS A STATE MODEL, NOT A GUARANTEED PRICE MODEL

The adoption curve describes institutional ownership behavior.

It does not guarantee that price will move in the same direction.

A company may move from Seeded to Emerging while its share price falls.

A company may remain at Consensus while its share price rises.

A company may enter Distribution because managers reduce shares, even if the
public narrative remains positive.

The state model helps the system reason about:

    - Breadth.
    - Persistence.
    - Crowding.
    - Room for future adoption.
    - Evidence decay.
    - Upgrade and downgrade logic.

It is a capital-organization model.

It is not a promise of return.
"""


INSTITUTIONAL_ADOPTION_CURVE = (
    "Absent",
    "Seeded",
    "Emerging",
    "Confirmed",
    "Consensus",
    "Saturated",
    "Distribution",
)


ADOPTION_STAGE_DEFINITIONS = {
    "Absent": (
        "The security or business function has no meaningful representation "
        "among relevant managers."
    ),
    "Seeded": (
        "One or a small number of relevant funds establish initial exposure. "
        "The evidence remains preliminary."
    ),
    "Emerging": (
        "Participation, aggregate shares, or theme breadth begins to expand. "
        "The signal is developing but not yet fully confirmed."
    ),
    "Confirmed": (
        "Multiple sufficiently independent managers show persistent and "
        "relevant adoption. The evidence survives initial falsification tests."
    ),
    "Consensus": (
        "The strategy or security is broadly recognized and substantially "
        "represented. The opportunity may remain attractive, but ownership "
        "formation is no longer early."
    ),
    "Saturated": (
        "Exposure is highly crowded, room for incremental allocation is "
        "reduced, and the strategy may be vulnerable to expectation "
        "compression."
    ),
    "Distribution": (
        "Managers are reducing shares, exiting positions, narrowing "
        "participation, or reallocating away from the strategy."
    ),
}


ADOPTION_STAGE_POLICY = """
Stage assignment MUST use explicit rules from `model_policy.json`.

An inference agent may explain a stage assignment but may not invent or
override it.
"""


ADOPTION_STAGE_TRANSITION_EXAMPLES = {
    "Absent_to_Seeded": (
        "A first relevant manager initiates a nontrivial position."
    ),
    "Seeded_to_Emerging": (
        "Additional relevant managers initiate or aggregate shares begin to "
        "rise persistently."
    ),
    "Emerging_to_Confirmed": (
        "Independent breadth and persistence satisfy confirmation thresholds."
    ),
    "Confirmed_to_Consensus": (
        "Ownership becomes broad and materially represented across the "
        "relevant universe."
    ),
    "Consensus_to_Saturated": (
        "Crowding rises while incremental adoption and room to grow decline."
    ),
    "Any_stage_to_Distribution": (
        "Persistent reductions, exits, narrowing breadth, or theme migration "
        "satisfy distribution rules."
    ),
}


# ------------------------------------------------------------------------------
# 12.6 STRATEGIC DIFFUSION
# ------------------------------------------------------------------------------

STRATEGIC_DIFFUSION_NARRATIVE = """
⬜ HOW A THEME SPREADS

A strategic function may first appear in a specialist fund.

It may later appear in:

    - A broader thematic fund.
    - A sector fund.
    - An active broad fund.
    - A benchmark-oriented portfolio.

That progression may indicate that the market is moving from specialist
recognition toward broader institutional acceptance.

But diffusion can also be mechanical.

The system must distinguish:

    STRATEGIC DIFFUSION
        Independent managers adopt the function for deliberate reasons.

    MECHANICAL DIFFUSION
        Index rules, benchmark changes, or common methodologies spread the
        position without independent research decisions.
"""


STRATEGIC_DIFFUSION = """
Strategic Diffusion measures whether a business function is spreading across
adjacent fund categories.
"""


STRATEGIC_DIFFUSION_SEQUENCE = (
    "specialist thematic",
    "broader thematic",
    "active broad",
    "benchmark adoption",
)


STRATEGIC_DIFFUSION_POLICY = """
Diffusion MAY strengthen a signal when it reflects independent strategic
adoption.
"""


STRATEGIC_DIFFUSION_PENALTIES = (
    "Index inclusion.",
    "Common benchmark methodology.",
    "Mechanical reconstitution.",
    "Shared portfolio teams.",
    "Broad market beta.",
    "Corporate actions.",
)


# ------------------------------------------------------------------------------
# 12.7 PERSISTENCE
# ------------------------------------------------------------------------------

PERSISTENCE_NARRATIVE = """
⬜ THE SYSTEM SHOULD NOT OVERREACT TO ONE FILE

A single disclosure change can be meaningful.

It can also be:

    - A correction.
    - A flow effect.
    - A basket anomaly.
    - A temporary rebalance.
    - A parser error.
    - A short-lived hedge.
    - A corporate-action artifact.

Persistence allows time to test whether the behavior repeats.

The correct window depends on:

    - Fund type.
    - Disclosure cadence.
    - Management style.
    - Rebalance schedule.
    - Strategy horizon.
    - Expected turnover.

Persistence therefore belongs in configurable policy rather than intuition.
"""


PERSISTENCE_PRINCIPLE = """
A one-day or one-disclosure change is a clue.

Persistence determines whether the clue becomes a pattern.
"""


PERSISTENCE_FACTORS = (
    "Consecutive disclosure persistence.",
    "Rolling-window persistence.",
    "Repeated additions.",
    "Stability through price volatility.",
    "Stability across market regimes.",
    "Persistence after earnings or policy events.",
    "Persistence across independent managers.",
)


PERSISTENCE_POLICY_LOCATION = """
The relevant windows and decay functions MUST be declared in
`model_policy.json`.
"""


# ------------------------------------------------------------------------------
# 12.8 CONFIDENCE
# ------------------------------------------------------------------------------

CONFIDENCE_NARRATIVE = """
⬜ A SINGLE CONFIDENCE NUMBER HIDES TOO MUCH

A system may be highly confident that:

    - It parsed the correct file.

But less confident that:

    - The security mapping is correct.

It may be confident that:

    - Adoption is rising.

But less confident that:

    - The available option is a suitable implementation.

Combining those judgments into one number would hide the weak link.

EDGE-TF therefore maintains separate confidence dimensions.

The overall confidence cannot erase a low critical component.
"""


CONFIDENCE_COMPONENTS = (
    "data_confidence",
    "classification_confidence",
    "signal_confidence",
    "validation_confidence",
    "implementation_confidence",
    "overall_confidence",
)


CONFIDENCE_POLICY = """
The system MUST keep the confidence components separate.

A single undifferentiated confidence score is insufficient.

A high signal score with low data confidence MUST NOT be presented as a
high-confidence trade.
"""


# ------------------------------------------------------------------------------
# 12.9 MISSING DATA
# ------------------------------------------------------------------------------

MISSING_DATA_NARRATIVE = """
⬜ MISSING IS A STATE, NOT A ZERO

A zero share change means the system observed no share change.

A missing share count means the system does not know the share change.

Those are not equivalent.

Replacing missing values with zero can create false stability.

Replacing an unknown manager relationship with full independence can inflate
cross-manager confirmation.

Replacing missing liquidity with adequate liquidity can create execution risk.

Every critical feature therefore requires an explicit missing-data policy.
"""


MISSING_DATA_POLICY = """
Missing data MUST NOT be silently converted to zero.
"""


MISSING_DATA_ACTIONS = (
    "hard_veto",
    "quarantine",
    "confidence_reduction",
    "feature_omission",
    "fallback_calculation",
    "warning_only",
)


DEFAULT_MISSING_DATA_BEHAVIOR = """
The default production behavior for missing critical disclosure fields is fail
closed.
"""


# ==============================================================================
# 13. GOVERNANCE POLICY
# ==============================================================================

# ------------------------------------------------------------------------------
# 13.1 PURPOSE
# ------------------------------------------------------------------------------

GOVERNANCE_NARRATIVE = """
⬜ GOVERNANCE IS THE SYSTEM'S RIGHT TO SAY NO

Research systems are often optimized to find opportunities.

Production systems must also be optimized to reject them.

A trade may be rejected because:

    - The evidence is weak.
    - The evidence is strong but the source is stale.
    - The thesis is valid but the portfolio is already concentrated.
    - The security is attractive but the market is too illiquid.
    - The option offers convexity but has an unacceptable spread.
    - The duration does not match the thesis.
    - The required approval is absent.
    - The broker or audit service is unavailable.
    - A kill switch is active.

Governance is not a second model.

It is a deterministic authority layer.
"""


GOVERNANCE_POLICY_PURPOSE = """
`governance_policy.json` contains deterministic controls that limit or prevent
trade execution.

The model may score.

The inference layer may recommend.

Governance may veto.

The model and inference layers may never override governance.
"""


# ------------------------------------------------------------------------------
# 13.2 GOVERNANCE CATEGORIES
# ------------------------------------------------------------------------------

GOVERNANCE_CATEGORIES = (
    "data_integrity",
    "portfolio_exposure",
    "position_sizing",
    "concentration",
    "correlation",
    "liquidity",
    "options",
    "leverage",
    "path_dependency",
    "market_regime",
    "execution_session",
    "broker_state",
    "human_approval",
    "kill_switch",
)


# ------------------------------------------------------------------------------
# 13.3 HARD VETOES
# ------------------------------------------------------------------------------

HARD_VETO_NARRATIVE = """
🟥 A HARD VETO IS NOT A NEGATIVE SCORE

A soft penalty says:

    The trade may continue with less confidence or less size.

A hard veto says:

    The action cannot continue.

That distinction should be visible in code, logs, user interfaces, and audit
records.

A hard veto should identify:

    - The rule that fired.
    - The observed value.
    - The policy threshold.
    - The time of the decision.
    - The affected action.
    - The required remediation.
"""


PRODUCTION_HARD_VETOES = (
    "Unverified source.",
    "Stale disclosure.",
    "Stale market data.",
    "Missing decision cutoff.",
    "Unknown disclosure artifact.",
    "Failed schema validation.",
    "Failed cross-file invariant.",
    "Unresolved corporate action.",
    "Unresolved ticker or identifier mapping.",
    "Insufficient liquidity.",
    "Excessive estimated market impact.",
    "Position-size breach.",
    "Portfolio-concentration breach.",
    "Gross-exposure breach.",
    "Net-exposure breach.",
    "Correlation-cluster breach.",
    "Options-liquidity breach.",
    "Expiration shorter than the required thesis horizon.",
    "Invalid or unavailable contract.",
    "Prohibited leverage or path dependency.",
    "Missing human approval.",
    "Broker connectivity or account-state failure.",
    "Active emergency kill switch.",
)


HARD_VETO_POLICY = """
Production execution MUST fail closed when any applicable hard veto is active.
"""


# ------------------------------------------------------------------------------
# 13.4 SOFT PENALTIES
# ------------------------------------------------------------------------------

SOFT_PENALTY_NARRATIVE = """
🟨 SOFT PENALTIES PRESERVE INFORMATION WITHOUT PRETENDING IT IS EQUAL

Not every weakness should destroy a signal.

A shared index methodology may reduce independence without making the evidence
worthless.

A wide but tradable spread may reduce position size without prohibiting a
trade.

A short history may reduce confidence while keeping the candidate under
observation.

Soft penalties allow the system to represent degrees of weakness.

The penalty calculation must still be deterministic and versioned.
"""


SOFT_PENALTY_TARGETS = (
    "Signal score.",
    "Confidence.",
    "Permissible position size.",
    "Permissible option premium.",
    "Maximum holding period.",
    "Implementation priority.",
)


POTENTIAL_SOFT_PENALTIES = (
    "Shared manager cluster.",
    "Shared index methodology.",
    "Passive inclusion.",
    "Price-only weight increase.",
    "Low mandate relevance.",
    "Low holdings purity.",
    "High crowding.",
    "Saturated adoption stage.",
    "Wide but nonprohibitive spreads.",
    "Short history.",
    "High mapping ambiguity.",
    "Incomplete theme confirmation.",
    "Divergence across relevant managers.",
)


# ------------------------------------------------------------------------------
# 13.5 POSITION AND PORTFOLIO LIMITS
# ------------------------------------------------------------------------------

PORTFOLIO_LIMIT_NARRATIVE = """
⬜ POSITION RISK CANNOT BE EVALUATED IN ISOLATION

A proposed position may be small by itself and still create excessive risk.

The portfolio may already contain:

    - Correlated securities.
    - Multiple companies serving the same business function.
    - Several ETFs holding overlapping underlying names.
    - Options with similar directional exposure.
    - Hidden leverage.
    - Concentrated exposure to one manager cluster or theme.

Governance must evaluate the proposed trade against the complete portfolio
state.

The relevant exposure may be economic rather than ticker-based.
"""


GOVERNANCE_LIMIT_FIELDS = (
    "maximum_single_position_pct_nav",
    "maximum_theme_exposure_pct_nav",
    "maximum_manager_cluster_exposure_pct_nav",
    "maximum_correlated_cluster_exposure_pct_nav",
    "maximum_options_premium_pct_nav",
    "maximum_total_options_premium_pct_nav",
    "maximum_gross_exposure",
    "maximum_net_exposure",
    "maximum_leverage",
    "maximum_daily_turnover",
    "maximum_estimated_market_impact",
    "maximum_allowed_spread",
    "minimum_average_daily_volume",
    "minimum_options_open_interest",
    "minimum_days_to_expiration",
)


GOVERNANCE_LIMIT_POLICY = """
All numeric limits MUST be defined in `governance_policy.json`.

Risk limits MUST be interpreted conservatively.

Environment profiles may tighten these values.

They may not loosen them.
"""


# ------------------------------------------------------------------------------
# 13.6 OPTIONS AND DURATION MATCHING
# ------------------------------------------------------------------------------

DURATION_MATCHING_NARRATIVE = """
⬜ THE INSTRUMENT MUST SURVIVE THE THESIS

A correct strategic thesis can still lose money when implemented with the
wrong duration.

A short-dated option may expire before institutional adoption becomes visible
in price.

A long-dated option may be unjustified when the only evidence is a temporary
gamma event.

A leveraged ETF may produce unexpected long-horizon results because daily
reset and path dependency alter the exposure.

The implementation layer therefore asks:

    - How long should the thesis take?
    - What could happen before it matures?
    - How much time decay is acceptable?
    - How much implied volatility is being purchased?
    - Can the position survive a delayed catalyst?
    - Is the payoff consistent with the evidence?
"""


THESIS_HORIZONS = (
    "short_term_event",
    "multi_week_repricing",
    "multi_quarter_adoption",
    "multi_year_structural_theme",
)


DURATION_MATCHING_POLICY = """
An option structure MUST match the expected duration of the underlying thesis.

A short-lived options event MUST NOT, by itself, justify a long-duration trade.

A long-duration adoption thesis SHOULD NOT be implemented with a contract whose
expiration does not provide adequate time for the thesis to develop.
"""


OPTIONS_POLICY_FACTORS = (
    "Days to expiration.",
    "Delta.",
    "Gamma.",
    "Theta.",
    "Vega.",
    "Implied volatility.",
    "Bid-ask spread.",
    "Open interest.",
    "Volume.",
    "Strike density.",
    "Event calendar.",
    "Earnings dates.",
    "Early exercise considerations.",
    "Liquidity under stress.",
    "Maximum premium at risk.",
)


PERMITTED_IMPLEMENTATIONS = (
    "Underlying shares.",
    "An ETF.",
    "A basket.",
    "A high-delta LEAP.",
    "A near-the-money LEAP.",
    "A call spread.",
    "A put spread.",
    "A collar.",
    "A hedge overlay.",
    "No trade.",
)


NO_TRADE_POLICY = """
The system MUST permit `NO_TRADE` as a valid final output.
"""


# ------------------------------------------------------------------------------
# 13.7 LEVERAGED AND INVERSE ETFS
# ------------------------------------------------------------------------------

LEVERAGED_ETF_NARRATIVE = """
⬜ A LEVERAGED ETF IS A PATH-DEPENDENT INSTRUMENT

The daily target of a leveraged ETF does not imply the same multiple over a
multi-month holding period.

The realized result depends on:

    - Sequence of returns.
    - Volatility.
    - Daily rebalancing.
    - Financing.
    - Tracking.
    - Fees.
    - Liquidity.

A leveraged ETF may be useful for a carefully defined tactical implementation.

It should not be treated as a simple substitute for long-duration exposure.
"""


LEVERAGED_AND_INVERSE_POLICY = """
Leveraged and inverse ETFs MAY be registered as implementation or hedge
candidates.

They SHOULD generally be excluded from institutional-intent inference because
daily rebalancing can create mechanical holdings changes.
"""


LONG_HORIZON_LEVERAGED_ETF_FACTORS = (
    "Path dependency.",
    "Daily reset mechanics.",
    "Volatility drag.",
    "Compounding effects.",
    "Financing costs.",
    "Tracking error.",
    "Liquidity under stress.",
)


LEVERAGED_MULTIPLE_WARNING = """
A leveraged or inverse ETF MUST NOT be treated as a simple long-duration
multiple of its benchmark.
"""


# ------------------------------------------------------------------------------
# 13.8 EMERGENCY KILL SWITCH
# ------------------------------------------------------------------------------

KILL_SWITCH_NARRATIVE = """
🟥 THE KILL SWITCH EXISTS FOR CONDITIONS THE NORMAL PIPELINE SHOULD NOT HANDLE

The ordinary governance engine evaluates known policy conditions.

The kill switch handles exceptional states requiring immediate interruption.

Examples may include:

    - Suspected configuration corruption.
    - Broker malfunction.
    - Duplicate order behavior.
    - Audit-log failure.
    - Severe data-quality failure.
    - Unauthorized access.
    - Market dislocation.
    - Uncontrolled position creation.
    - Model behavior outside tested bounds.

A kill switch may apply to the entire system or to a narrow scope.

Its activation and release must both be auditable.
"""


KILL_SWITCH_SCOPES = (
    "all_execution",
    "new_positions",
    "options_only",
    "specific_broker",
    "specific_account",
    "specific_strategy",
    "specific_theme",
    "specific_instrument",
    "specific_source",
)


KILL_SWITCH_RECORD_REQUIREMENTS = (
    "Triggering condition.",
    "Activating user or system.",
    "Timestamp.",
    "Scope.",
    "Affected decisions.",
    "Required remediation.",
    "Approval required for release.",
)


KILL_SWITCH_POLICY = """
The emergency kill switch MUST override all other layers.

An inference agent MUST NOT deactivate a kill switch.
"""


# ==============================================================================
# 14. POINT-IN-TIME AND CAUSAL TIMESTAMPING
# ==============================================================================

POINT_IN_TIME_NARRATIVE = """
⬜ THE MOST DANGEROUS BACKTEST ERROR CAN LOOK LIKE INTELLIGENCE

A historical model can appear powerful when it uses information that was not
actually available at the decision time.

This can happen through:

    - Later corrections.
    - Backfilled publication times.
    - Revised holdings.
    - Updated identifiers.
    - Restated corporate actions.
    - Survivorship-biased fund universes.
    - Current ontology mappings applied retroactively without labeling.
    - Files downloaded after the market opened but treated as premarket data.

Point-in-time integrity is therefore not a database convenience.

It is a causal requirement.

The system must reconstruct what could have been known, not what is known now.
"""


# ------------------------------------------------------------------------------
# 14.1 REQUIRED TIMESTAMPS
# ------------------------------------------------------------------------------

REQUIRED_TIMESTAMPS = (
    "portfolio_as_of",
    "published_at",
    "first_observed_at",
    "download_started_at",
    "download_completed_at",
    "ingested_at",
    "normalized_at",
    "decision_cutoff_at",
    "source_revision_at",
)


TIMESTAMP_POLICY = """
All timestamps MUST use ISO 8601 format with explicit timezone information.

UTC is the canonical storage timezone.
"""


TIMESTAMP_MEANINGS = {
    "portfolio_as_of": (
        "The effective date or time of the portfolio represented by the source."
    ),
    "published_at": (
        "The time the publisher made the artifact available, when verifiable."
    ),
    "first_observed_at": (
        "The first time EDGE-TF actually observed the artifact."
    ),
    "download_started_at": (
        "The start of the source retrieval."
    ),
    "download_completed_at": (
        "The completion of the source retrieval."
    ),
    "ingested_at": (
        "The time the raw artifact entered the internal data system."
    ),
    "normalized_at": (
        "The time normalized observations were produced."
    ),
    "decision_cutoff_at": (
        "The latest allowable information time for the decision."
    ),
    "source_revision_at": (
        "The publication or observation time of a corrected source version."
    ),
}


# ------------------------------------------------------------------------------
# 14.2 DECISION ELIGIBILITY RULE
# ------------------------------------------------------------------------------

DECISION_ELIGIBILITY_RULE = """
A record may support a historical or live decision only when:

    published_at <= decision_cutoff_at

AND

    first_observed_at <= decision_cutoff_at

AND

    the exact source revision existed at decision_cutoff_at

AND

    the parser version was valid for that source revision
"""


UNKNOWN_PUBLICATION_TIME_POLICY = """
When `published_at` cannot be established, production historical simulation
MUST treat the record as ineligible unless a documented conservative fallback
policy applies.
"""


# ------------------------------------------------------------------------------
# 14.3 REVISIONS
# ------------------------------------------------------------------------------

REVISION_NARRATIVE = """
⬜ CORRECTION DOES NOT ERASE THE ORIGINAL DECISION ENVIRONMENT

Suppose an issuer publishes a file at 8:00 a.m.

EDGE-TF uses that file at 9:00 a.m.

The issuer corrects it at noon.

The corrected file may improve current knowledge.

It was not available at 9:00 a.m.

The historical decision must continue to reference the original file.

A revised analysis may be generated, but it must be labeled as revised.
"""


REVISION_POLICY = """
Issuer corrections MUST be represented as new source revisions.
"""


REVISION_RECORD_REQUIREMENTS = (
    "Original artifact.",
    "Corrected artifact.",
    "Time correction was published.",
    "Time correction was first observed.",
    "Records affected.",
    "Decisions affected.",
)


HISTORICAL_REVISION_POLICY = """
Historical decisions MUST NOT be silently recomputed using later corrections
unless the analysis is explicitly labeled as revised or restated.
"""


# ==============================================================================
# 15. DATA QUALITY AND QUARANTINE
# ==============================================================================

DATA_QUALITY_NARRATIVE = """
⬜ QUARANTINE PROTECTS THE PIPELINE FROM CONFIDENTLY USING BAD DATA

A data-quality warning should not merely appear in a log while the same record
continues through scoring.

When a critical field cannot be trusted, the record should be isolated.

Quarantine preserves the artifact for investigation while preventing it from
entering:

    - Feature calculations.
    - IAV scoring.
    - Adoption-stage assignment.
    - Trade design.
    - Production execution.

This is especially important for agentic systems because an inference agent
may produce convincing language from incomplete data.

The data gate must operate before narrative confidence is generated.
"""


# ------------------------------------------------------------------------------
# 15.1 DATA-QUALITY CHECKS
# ------------------------------------------------------------------------------

DATA_QUALITY_CHECKS = (
    "File availability.",
    "File type.",
    "Content hash.",
    "Header signature.",
    "Required columns.",
    "Record count.",
    "Duplicate rows.",
    "Identifier validity.",
    "Ticker and CUSIP consistency.",
    "Share-count numeric validity.",
    "Weight numeric validity.",
    "Market-value validity.",
    "Weight-sum tolerance.",
    "Currency consistency.",
    "Effective date.",
    "Publication date.",
    "Unexpected cash treatment.",
    "Unexpected derivative treatment.",
    "Sudden universe replacement.",
    "Corporate-action anomalies.",
    "Parser coverage.",
)


# ------------------------------------------------------------------------------
# 15.2 QUARANTINE REASONS
# ------------------------------------------------------------------------------

QUARANTINE_REASON_CODES = (
    "SOURCE_UNAVAILABLE",
    "SOURCE_UNVERIFIED",
    "SOURCE_STALE",
    "ARTIFACT_UNKNOWN",
    "FORMAT_CHANGED",
    "HEADER_MISMATCH",
    "PARSE_FAILURE",
    "PARTIAL_PARSE",
    "WEIGHT_SUM_FAILURE",
    "DUPLICATE_RECORDS",
    "IDENTIFIER_CONFLICT",
    "CORPORATE_ACTION_UNRESOLVED",
    "TIMESTAMP_UNKNOWN",
    "PUBLICATION_LATE",
    "REVISION_PENDING",
    "ONTOLOGY_MAPPING_MISSING",
    "CLUSTER_MAPPING_MISSING",
    "LIQUIDITY_DATA_STALE",
    "MARKET_DATA_STALE",
)


QUARANTINE_POLICY = """
A quarantined observation MUST NOT enter production scoring or execution.
"""


# ------------------------------------------------------------------------------
# 15.3 FAIL-CLOSED PRINCIPLE
# ------------------------------------------------------------------------------

FAIL_CLOSED_NARRATIVE = """
🟥 WHY UNKNOWN DOES NOT DEFAULT TO SAFE

A permissive default is convenient.

It is also dangerous.

If the system does not know whether two funds share a portfolio team, it
cannot assume independence.

If the system does not know whether a file is full holdings, it cannot assume
completeness.

If the system does not know current liquidity, it cannot assume the order can
be executed safely.

Fail-closed behavior may reduce the number of trades.

That is an acceptable cost of protecting the integrity of production
decisions.
"""


FAIL_CLOSED_PRINCIPLE = """
Unknown is not neutral.

Unknown is ineligible until resolved.
"""


PROHIBITED_UNKNOWN_ASSUMPTIONS = (
    "Missing shares as zero shares.",
    "Missing weight as zero weight.",
    "Missing publication time as premarket publication.",
    "Missing manager relationships as independence.",
    "Missing ontology mapping as unrelated exposure.",
    "Missing liquidity data as adequate liquidity.",
)


# ==============================================================================
# 16. CROSS-FILE INVARIANTS
# ==============================================================================

CROSS_FILE_INVARIANT_NARRATIVE = """
⬜ VALID JSON CAN STILL DESCRIBE AN INVALID SYSTEM

A file can pass its individual schema while still conflicting with another
file.

Examples:

    - A fund references a source that does not exist.
    - A theme identifier has been retired.
    - A profile loosens a base risk limit.
    - A signal-eligible fund has no verified artifact.
    - A model references a missing feature.
    - Two active fund records overlap in time.
    - The manifest declares 80 active funds but only 79 resolve.

Cross-file invariants test the complete registry as a system.
"""


CROSS_FILE_INVARIANTS = (
    "Every `fund_id` is unique.",
    "Every active fund has at least one active listing.",
    "No fund has overlapping effective-date records.",
    "Every `source_id` referenced by a fund exists in "
    "`source_registry.json`.",
    "Every manager-cluster identifier exists in `manager_clusters.json`.",
    "Every theme identifier exists in `strategy_ontology.json`.",
    "Every function identifier exists in `strategy_ontology.json`.",
    "Every system role is a permitted enum value.",
    "Every signal-eligible fund has a verified source.",
    "Every signal-eligible source has a recognized artifact type.",
    "No tracking basket is marked as complete holdings without explicit "
    "verification.",
    "Every implementation-eligible fund has a liquidity policy profile.",
    "Every options-eligible fund has an options execution policy.",
    "Every production fund has current governance approval.",
    "Every production bundle has valid hashes.",
    "Every production bundle has an approved profile.",
    "Every production profile is at least as restrictive as the base "
    "governance policy.",
    "No active kill switch is overridden by another file.",
    "Every model feature referenced by scoring logic has a defined "
    "missing-data policy.",
    "Every adoption-stage threshold is ordered and nonoverlapping.",
    "Every ontology mapping includes an effective date and review status.",
    "No proposed ontology mapping is used as an approved production mapping.",
    "Every execution decision can be reproduced from a specific configuration "
    "bundle.",
    "The active fund count matches the count declared in `manifest.json`.",
)


INVARIANT_FAILURE_POLICY = """
Any invariant failure MUST prevent production startup.
"""


# ==============================================================================
# 17. ENVIRONMENT PROFILES
# ==============================================================================

ENVIRONMENT_PROFILE_NARRATIVE = """
⬜ THE SAME CODE SHOULD NOT HAVE THE SAME PERMISSIONS EVERYWHERE

Research needs flexibility.

Production needs restriction.

A research environment may allow:

    - Experimental features.
    - Draft ontology mappings.
    - Incomplete historical datasets.
    - Alternative model weights.
    - Exploratory agent prompts.

Production must require:

    - Approved sources.
    - Approved ontology.
    - Approved models.
    - Current data.
    - Deterministic governance.
    - Human approval where required.
    - Full audit.

Environment profiles make those differences explicit without requiring
separate codebases.
"""


# ------------------------------------------------------------------------------
# 17.1 RESEARCH PROFILE
# ------------------------------------------------------------------------------

RESEARCH_PROFILE = {
    "file": "profiles/research.json",
    "permitted": (
        "Historical analysis.",
        "Backtesting.",
        "Feature development.",
        "Ontology research.",
        "Source evaluation.",
        "Model experimentation.",
        "Research-agent output.",
    ),
    "prohibited": (
        "Broker connection.",
        "Live order submission.",
        "Production approval.",
        "Production configuration mutation.",
    ),
    "label_requirement": (
        "Research output MUST be labeled as nonproduction."
    ),
}


# ------------------------------------------------------------------------------
# 17.2 PAPER PROFILE
# ------------------------------------------------------------------------------

PAPER_PROFILE = {
    "file": "profiles/paper.json",
    "permitted": (
        "Live or delayed disclosure ingestion.",
        "Live market-data evaluation.",
        "Simulated orders.",
        "Simulated portfolio accounting.",
        "Shadow governance testing.",
        "Human-review workflow testing.",
    ),
    "prohibited": (
        "Live order submission.",
        "Real capital deployment.",
        "Production secret access unless explicitly required for read-only "
        "connectivity.",
    ),
    "governance_policy": (
        "Paper trading SHOULD use the same or stricter governance controls as "
        "production."
    ),
}


# ------------------------------------------------------------------------------
# 17.3 PRODUCTION PROFILE
# ------------------------------------------------------------------------------

PRODUCTION_PROFILE = {
    "file": "profiles/production.json",
    "permitted": (
        "Verified live data.",
        "Approved models.",
        "Approved ontology.",
        "Approved governance.",
        "Live broker interaction through the execution gateway.",
        "Live order submission after all required gates.",
    ),
    "requirements": (
        "Valid signed configuration bundle.",
        "No failed invariants.",
        "No applicable kill switch.",
        "Current data.",
        "Deterministic governance approval.",
        "Required human approval.",
        "Broker preflight validation.",
        "Full audit logging.",
    ),
}


# ------------------------------------------------------------------------------
# 17.4 PROFILE OVERRIDE POLICY
# ------------------------------------------------------------------------------

PROFILE_TIGHTENING_PERMISSIONS = (
    "Position limits.",
    "Exposure limits.",
    "Liquidity thresholds.",
    "Human approval requirements.",
    "Permitted instruments.",
    "Permitted order types.",
    "Permitted operating hours.",
)


PROFILE_OVERRIDE_PROHIBITIONS = (
    "Loosen a hard governance limit.",
    "Change fund identity.",
    "Change source truth.",
    "Change manager relationships.",
    "Change ontology meaning.",
    "Mark an unverified source as verified.",
    "Disable audit logging.",
    "Disable the kill switch.",
)


PROFILE_MONOTONICITY_RULE = """
A child profile may become more restrictive.

It may not become less restrictive than the governing base policy.
"""


# ==============================================================================
# 18. AGENT PERMISSIONS AND HUMAN GATES
# ==============================================================================

AGENT_BOUNDARY_NARRATIVE = """
⬜ AGENTS ARE REASONING COMPONENTS, NOT GOVERNING AUTHORITIES

Agents are useful where the task requires interpretation.

Examples:

    - Classifying a business model.
    - Summarizing a disclosure pattern.
    - Proposing alternative explanations.
    - Comparing implementation structures.
    - Identifying missing evidence.
    - Drafting a research dossier.

Agents are weaker where the task requires deterministic authority.

Examples:

    - Enforcing a maximum position size.
    - Confirming that a source hash matches.
    - Verifying a contract symbol.
    - Confirming that approval exists.
    - Blocking execution during a kill switch.
    - Preserving an audit record.

EDGE-TF therefore uses agents inside a deterministic control envelope.
"""


# ------------------------------------------------------------------------------
# 18.1 PERMITTED AGENT ACTIONS
# ------------------------------------------------------------------------------

PERMITTED_AGENT_ACTIONS = (
    "Parse approved source artifacts.",
    "Propose identifier resolutions.",
    "Propose ontology mappings.",
    "Calculate model features.",
    "Calculate IAV and related metrics.",
    "Generate research summaries.",
    "Produce trade-design alternatives.",
    "Identify disconfirming evidence.",
    "Recommend `NO_TRADE`.",
    "Generate confidence explanations.",
    "Flag stale or inconsistent data.",
    "Escalate to human review.",
)


# ------------------------------------------------------------------------------
# 18.2 PROHIBITED AGENT ACTIONS
# ------------------------------------------------------------------------------

PROHIBITED_AGENT_ACTIONS = (
    "Modify the active production configuration.",
    "Approve their own ontology changes.",
    "Change governance limits.",
    "Override a hard veto.",
    "Disable a kill switch.",
    "Mark a source as verified.",
    "Treat an unknown artifact as complete holdings.",
    "Fabricate missing data.",
    "Suppress disconfirming evidence.",
    "Submit orders directly to a broker.",
    "Increase a proposed position after governance sizing.",
    "Change a human approval record.",
    "Alter an audit log.",
    "Store credentials in prompts or configuration.",
)


# ------------------------------------------------------------------------------
# 18.3 DETERMINISTIC POST-AGENT VALIDATION
# ------------------------------------------------------------------------------

POST_AGENT_VALIDATION_NARRATIVE = """
⬜ EVERY AGENT OUTPUT IS UNTRUSTED UNTIL REVALIDATED

An agent may return a structurally correct recommendation containing a stale
ticker.

It may describe an option that no longer exists.

It may reference a fund that has become ineligible.

It may size a trade before the portfolio changes.

It may overlook a newly activated kill switch.

For that reason, the system validates the final proposed action after all
agent reasoning is complete.

The execution gateway should accept a deterministic order packet.

It should never accept prose as authorization.
"""


POST_AGENT_VALIDATION_REQUIREMENTS = (
    "Instrument identity.",
    "Fund and security eligibility.",
    "Current configuration bundle.",
    "Data freshness.",
    "Signal provenance.",
    "Governance compliance.",
    "Position sizing.",
    "Portfolio limits.",
    "Liquidity.",
    "Order validity.",
    "Options contract validity.",
    "Human approval.",
    "Kill-switch state.",
)


AGENT_EXECUTION_POLICY = """
Every proposed trade MUST pass deterministic validation after the final agent
output.

Agent-generated text is never an execution authorization.
"""


# ------------------------------------------------------------------------------
# 18.4 HUMAN APPROVAL TIERS
# ------------------------------------------------------------------------------

HUMAN_GATE_NARRATIVE = """
🟧 HUMAN APPROVAL SHOULD BE RISK-BASED

Human review should not be a ceremonial click.

The reviewer should receive:

    - The strategic thesis.
    - The disclosure evidence.
    - The IAV components.
    - The alternative explanations.
    - The proposed implementation.
    - The maximum loss.
    - The portfolio impact.
    - The warnings.
    - The hard-veto state.
    - The data cutoff.
    - The active configuration bundle.

Higher-risk actions should require stronger approval.
"""


HUMAN_APPROVAL_TIERS = {
    "TIER_0": (
        "Research output only. No order."
    ),
    "TIER_1": (
        "Low-risk paper-trading order. Automated approval permitted."
    ),
    "TIER_2": (
        "Production order below enhanced-review threshold. One authorized "
        "human approval required."
    ),
    "TIER_3": (
        "Options, leverage, concentrated exposure, or elevated volatility. "
        "Two authorized approvals required."
    ),
    "TIER_4": (
        "Exceptional or policy-sensitive action. Investment committee or "
        "designated senior approval required."
    ),
}


APPROVAL_TIER_POLICY = """
The actual approval triggers belong in `governance_policy.json`.
"""


# ==============================================================================
# 19. AUDIT AND DECISION PROVENANCE
# ==============================================================================

AUDIT_NARRATIVE = """
⬜ AN EXPLANATION IS NOT AN AUDIT TRAIL

An agent-generated explanation may sound complete while omitting critical
facts.

A valid audit trail should make reconstruction mechanical.

A reviewer should be able to retrieve:

    - The exact raw source files.
    - The exact normalized observations.
    - The configuration bundle.
    - The model version.
    - The feature values.
    - The ontology mapping.
    - The agent and prompt versions.
    - The governance result.
    - The human approval.
    - The final order packet.
    - The broker response.
    - The subsequent position state.

The purpose is not only regulatory or operational defense.

Reproducibility is also necessary for model improvement.

The team cannot learn from a decision it cannot reconstruct.
"""


AUDIT_PRINCIPLE = """
Every research signal, trade design, governance result, and execution attempt
MUST be reproducible.
"""


# ------------------------------------------------------------------------------
# 19.1 REQUIRED DECISION RECORD
# ------------------------------------------------------------------------------

REQUIRED_DECISION_RECORD = {
    "decision_id": "8aaf9c48-02ad-4b55-bab1-56e991891f6d",
    "created_at": "2026-08-16T13:22:11Z",

    "configuration": {
        "bundle_version": "2.0.0-rc.1",
        "bundle_hash": "sha256:EXAMPLE",
        "schema_version": "2.0.0",
        "profile": "paper",
    },

    "data_cutoff_at": "2026-08-16T13:20:00Z",

    "source_snapshot_ids": [
        "snapshot_001",
        "snapshot_002",
    ],

    "models": {
        "iav_model_version": "iav_v2",
        "validation_model_version": "validation_v1",
    },

    "agents": [
        {
            "agent_id": "strategy_inference_agent",
            "version": "1.3.0",
            "prompt_version": "prompt_2.1.0",
        }
    ],

    "strategic_move": "industrial_operations_intelligence",

    "candidate_security_ids": [
        "security_us_example",
    ],

    "scores": {
        "data_confidence": 0.98,
        "classification_confidence": 0.92,
        "signal_confidence": 0.81,
        "validation_confidence": 0.74,
        "implementation_confidence": 0.69,
    },

    "governance": {
        "result": "APPROVED_FOR_PAPER",
        "vetoes": [],
        "warnings": [
            "OPTIONS_SPREAD_ELEVATED",
        ],
    },

    "human_approval_id": None,
    "final_action": "PAPER_ORDER",
}


# ------------------------------------------------------------------------------
# 19.2 AUDIT REQUIREMENTS
# ------------------------------------------------------------------------------

AUDIT_RECORD_REQUIREMENTS = (
    "Append-only.",
    "Timestamped.",
    "Content-hashed.",
    "Linked to the configuration bundle.",
    "Linked to source snapshots.",
    "Linked to model versions.",
    "Linked to prompt and agent versions.",
    "Linked to approvals.",
    "Linked to broker responses where applicable.",
)


AUDIT_MUTATION_POLICY = """
Agents and ordinary application processes MUST NOT delete or rewrite audit
records.
"""


AUDIT_REPLAY_QUESTIONS = (
    "What did the system know?",
    "When did it know it?",
    "How was the evidence classified?",
    "Which features were calculated?",
    "Which rules were applied?",
    "Which agent produced the recommendation?",
    "Which human approved it?",
    "What was sent to the broker?",
    "What did the broker return?",
    "What changed afterward?",
)


# ==============================================================================
# 20. RELEASE MANIFEST
# ==============================================================================

RELEASE_MANIFEST_NARRATIVE = """
⬜ THE MANIFEST MAKES MANY FILES ONE RELEASE

A directory can contain a valid mixture of incompatible files.

For example:

    - A new model policy.
    - An old ontology.
    - A partially updated fund universe.
    - A production profile from another branch.

The manifest identifies the exact set intended to operate together.

Hash verification ensures that the loaded files match the approved release.

The bundle hash should appear in every decision record.
"""


RELEASE_MANIFEST_PURPOSE = """
`manifest.json` identifies the complete configuration release.
"""


CANONICAL_RELEASE_MANIFEST = {
    "schema_version": "2.0.0",
    "bundle_version": "2.0.0-rc.1",
    "status": "release_candidate",

    "effective_at": "2026-08-16T00:00:00Z",
    "created_at": "2026-08-16T00:00:00Z",

    "git_commit": "REPLACE_WITH_COMMIT_HASH",

    "expected_active_fund_count": 80,

    "files": [
        {
            "path": "fund_universe.json",
            "sha256": "REPLACE_WITH_GENERATED_HASH",
        },
        {
            "path": "manager_clusters.json",
            "sha256": "REPLACE_WITH_GENERATED_HASH",
        },
        {
            "path": "source_registry.json",
            "sha256": "REPLACE_WITH_GENERATED_HASH",
        },
        {
            "path": "strategy_ontology.json",
            "sha256": "REPLACE_WITH_GENERATED_HASH",
        },
        {
            "path": "model_policy.json",
            "sha256": "REPLACE_WITH_GENERATED_HASH",
        },
        {
            "path": "governance_policy.json",
            "sha256": "REPLACE_WITH_GENERATED_HASH",
        },
    ],

    "approval": {
        "status": "pending",
        "required_approver_roles": [
            "research_governance",
            "risk_governance",
            "engineering_owner",
        ],
        "approvals": [],
    },

    "rollback": {
        "previous_bundle_version": "1.1.0",
        "previous_bundle_hash": "REPLACE_WITH_PREVIOUS_HASH",
    },
}


HASH_POLICY = """
Hash values MUST be generated automatically.

They MUST NOT be manually invented.
"""


# ==============================================================================
# 21. CHANGE-CONTROL RUNBOOK
# ==============================================================================

CHANGE_CONTROL_NARRATIVE = """
⬜ A CONFIGURATION CHANGE IS A SOFTWARE CHANGE

Changing a fund's eligibility can alter signals.

Changing an ontology mapping can alter theme exposure.

Changing an IAV weight can alter rankings.

Changing a risk threshold can alter real capital deployment.

Those changes require:

    - Review.
    - Testing.
    - Effective dating.
    - Approval.
    - Release identity.
    - Rollback.

Editing JSON directly in production is prohibited because it bypasses the
evidence and governance chain.
"""


CHANGE_CONTROL_SEQUENCE = (
    "Change Proposal",
    "Branch or Pull Request",
    "Schema Validation",
    "Cross-File Invariant Validation",
    "Unit Tests",
    "Historical Regression",
    "Point-in-Time Replay",
    "Governance Regression",
    "Paper or Shadow Deployment",
    "Independent Review",
    "Required Approvals",
    "Manifest Generation",
    "Bundle Hashing",
    "Release Signing",
    "Production Deployment",
    "Post-Deployment Monitoring",
)


# ------------------------------------------------------------------------------
# 21.1 CHANGE PROPOSAL
# ------------------------------------------------------------------------------

CHANGE_PROPOSAL_REQUIREMENTS = (
    "Files affected.",
    "Reason for change.",
    "Expected behavior change.",
    "Risk impact.",
    "Backtest impact.",
    "Production impact.",
    "Rollback plan.",
    "Required reviewers.",
)


# ------------------------------------------------------------------------------
# 21.2 VERSIONING
# ------------------------------------------------------------------------------

SEMANTIC_VERSION_FORMAT = "MAJOR.MINOR.PATCH"


MAJOR_VERSION_TRIGGERS = (
    "Schema redesign.",
    "New eligibility model.",
    "Changed risk-governance precedence.",
    "Changed ontology hierarchy.",
    "Changed definition of a core model feature.",
)


MINOR_VERSION_TRIGGERS = (
    "New fund.",
    "New ontology node.",
    "New source type.",
    "New model feature.",
    "New governance warning.",
)


PATCH_VERSION_TRIGGERS = (
    "Typographical correction.",
    "Corrected source metadata.",
    "Corrected manager-cluster relationship.",
    "Nonbehavioral documentation change.",
)


# ------------------------------------------------------------------------------
# 21.3 EFFECTIVE DATING
# ------------------------------------------------------------------------------

EFFECTIVE_DATING_POLICY = """
Configuration changes MUST be effective-dated.

A new release MUST NOT retroactively alter the configuration used by an
earlier recorded decision.

Historical analysis MAY intentionally load the configuration that was active at
a prior date.
"""


# ------------------------------------------------------------------------------
# 21.4 ROLLBACK
# ------------------------------------------------------------------------------

ROLLBACK_NARRATIVE = """
⬜ ROLLBACK RESTORES OPERATION; IT DOES NOT ERASE HISTORY

A failed release may need to be replaced quickly.

The previous valid bundle should already be known.

Rollback should not require reconstructing an old configuration from memory.

The system should preserve:

    - The failed bundle.
    - Why it failed.
    - When rollback occurred.
    - Which decisions used the failed bundle.
    - Whether any orders were affected.
    - What remediation remains open.
"""


ROLLBACK_POLICY = """
Every production release MUST identify a verified rollback target.
"""


ROLLBACK_RECORD_REQUIREMENTS = (
    "The failed release.",
    "The rollback reason.",
    "The activation time.",
    "Decisions made under the failed release.",
    "Orders submitted under the failed release.",
    "Required remediation.",
)


ROLLBACK_HISTORY_POLICY = """
Rollback does not erase history.
"""


# ==============================================================================
# 22. CONTINUOUS INTEGRATION REQUIREMENTS
# ==============================================================================

CI_NARRATIVE = """
⬜ THE REPOSITORY SHOULD REJECT INVALID POLICY BEFORE A HUMAN CAN DEPLOY IT

Reviewers should not need to manually discover:

    - Duplicate identifiers.
    - Broken references.
    - Invalid enum values.
    - Overlapping effective dates.
    - Missing model policies.
    - A production profile that loosens risk.
    - A source marked verified without required evidence.
    - Secrets committed to the repository.

Continuous integration converts those expectations into repeatable checks.

A pull request that changes configuration is incomplete until the tests explain
the behavioral impact.
"""


REQUIRED_CI_CHECKS = (
    "json_parse",
    "json_schema_validation",
    "manifest_completeness",
    "file_hash_generation",
    "unique_id_validation",
    "enum_validation",
    "effective_date_validation",
    "cross_file_reference_validation",
    "source_eligibility_validation",
    "ontology_reference_validation",
    "manager_cluster_validation",
    "profile_override_validation",
    "risk_limit_validation",
    "adoption_threshold_validation",
    "missing_data_policy_validation",
    "historical_regression",
    "point_in_time_replay",
    "governance_regression",
)


CI_FAILURE_POLICY = """
A configuration pull request MUST fail when any required check fails.
"""


CI_ADDITIONAL_DETECTIONS = (
    "Hard-coded duplicate thresholds in application code.",
    "Direct JSON access outside the approved loader.",
    "Secrets committed to configuration files.",
    "Unreviewed production ontology changes.",
    "Production sources marked verified without evidence.",
    "Profile overrides that loosen base policy.",
    "Missing release notes.",
    "Missing rollback target.",
)


# ==============================================================================
# 23. OPERATIONAL RUNBOOK
# ==============================================================================

OPERATIONAL_RUNBOOK_NARRATIVE = """
⬜ A NORMAL OPERATING DAY

A normal day begins before the model sees a trade.

The system first establishes whether it can trust its own operating state.

It validates:

    - The configuration bundle.
    - The environment profile.
    - The source registry.
    - The data services.
    - The kill-switch state.
    - The audit service.
    - The broker state, where applicable.

It then collects and preserves disclosures.

Only valid observations enter feature calculation.

Only valid features enter scoring.

Only validated signals enter trade design.

Only governed trade designs reach approval.

Only approved immutable order packets reach execution.

The runbook exists to keep that sequence from collapsing into one opaque agent
call.
"""


# ------------------------------------------------------------------------------
# 23.1 STARTUP
# ------------------------------------------------------------------------------

STARTUP_SEQUENCE = (
    "Load the selected environment profile.",
    "Load `manifest.json`.",
    "Verify hashes.",
    "Validate schemas.",
    "Validate cross-file invariants.",
    "Confirm bundle effective time.",
    "Confirm kill-switch state.",
    "Confirm source registry status.",
    "Confirm market-data and disclosure-data availability.",
    "Freeze the configuration snapshot.",
    "Record the startup snapshot hash.",
)


STARTUP_FAILURE_POLICY = """
Production startup MUST abort on any critical failure.
"""


# ------------------------------------------------------------------------------
# 23.2 DISCLOSURE INGESTION
# ------------------------------------------------------------------------------

DISCLOSURE_INGESTION_SEQUENCE = (
    "Determine whether a file is expected.",
    "Fetch the source.",
    "Preserve the raw artifact.",
    "Calculate the raw-file hash.",
    "Identify the artifact type.",
    "Validate the expected format.",
    "Parse with the registered parser profile.",
    "Normalize identifiers.",
    "Run data-quality checks.",
    "Record causal timestamps.",
    "Compare with the prior valid snapshot.",
    "Quarantine failures.",
    "Publish valid normalized observations.",
)


# ------------------------------------------------------------------------------
# 23.3 SIGNAL CALCULATION
# ------------------------------------------------------------------------------

SIGNAL_CALCULATION_SEQUENCE = (
    "Confirm source eligibility.",
    "Confirm point-in-time availability.",
    "Confirm ontology mapping.",
    "Confirm manager-cluster mapping.",
    "Calculate share-count changes.",
    "Calculate weight changes.",
    "Separate price contribution from manager action.",
    "Detect initiations, exits, additions, and reductions.",
    "Aggregate across relevant managers.",
    "Calculate IAV components.",
    "Apply persistence.",
    "Apply independence adjustments.",
    "Apply mandate-relevance and purity adjustments.",
    "Apply structural penalties.",
    "Assign an adoption stage.",
    "Generate confidence components.",
    "Record all feature provenance.",
)


# ------------------------------------------------------------------------------
# 23.4 VALIDATION AND FALSIFICATION
# ------------------------------------------------------------------------------

VALIDATION_NARRATIVE = """
⬜ VALIDATION IS AN ATTEMPT TO BREAK THE THESIS

The validation layer should not ask only:

    What confirms the trade?

It should ask:

    What else could explain the evidence?

Alternative explanations may include:

    - Price appreciation.
    - Passive inclusion.
    - Index reconstitution.
    - Corporate action.
    - Broad sector rotation.
    - Fund inflows.
    - Shared manager behavior.
    - Temporary hedging.
    - Short-lived options activity.
    - Valuation already reflecting the theme.

The system should reward a thesis for surviving disconfirmation.

It should not reward the quantity of bullish language.
"""


VALIDATION_AND_FALSIFICATION_SEQUENCE = (
    "Test whether the signal is price-driven.",
    "Test for index inclusion or reconstitution.",
    "Test for corporate actions.",
    "Test for common-manager dependence.",
    "Test for common-index dependence.",
    "Test for broad sector beta.",
    "Test for fund-flow distortions.",
    "Test fundamental durability.",
    "Test valuation risk.",
    "Test liquidity.",
    "Test options-market confirmation where relevant.",
    "Search for disconfirming evidence.",
    "Permit `NO_TRADE`.",
)


GAMMA_VALIDATION_POLICY = """
Gamma or options-flow evidence is a validation and timing layer.

It is not the foundational thesis.
"""


# ------------------------------------------------------------------------------
# 23.5 TRADE DESIGN
# ------------------------------------------------------------------------------

TRADE_DESIGN_NARRATIVE = """
⬜ THE FIRST TRADE IDEA SHOULD NOT AUTOMATICALLY BECOME THE FINAL TRADE

The research process may begin with an ETF.

Reverse engineering may reveal that:

    - The ETF is diluted by unrelated holdings.
    - A different ETF has greater thematic purity.
    - A small basket better captures the repeated strategic components.
    - One underlying company carries most of the intended exposure.
    - A single security creates excessive idiosyncratic risk.
    - Options provide useful convexity.
    - Options are too expensive.
    - A spread provides better defined risk.
    - A hedge is necessary.
    - No available vehicle justifies capital.

Trade design is an optimization problem constrained by evidence and risk.

It is not a ritual confirmation of the original idea.
"""


TRADE_DESIGN_ALTERNATIVES = (
    "Original ETF implementation.",
    "Alternative ETF implementation.",
    "Single-security implementation.",
    "Multi-security basket.",
    "Underlying shares.",
    "Long-duration options.",
    "Defined-risk spreads.",
    "Hedge overlays.",
    "No trade.",
)


TRADE_DESIGN_FACTORS = (
    "exposure_purity",
    "liquidity",
    "concentration",
    "correlation",
    "convexity",
    "volatility",
    "duration",
    "path_dependency",
    "transaction_cost",
    "maximum_loss",
    "governance_fit",
)


# ------------------------------------------------------------------------------
# 23.6 PRE-ORDER VALIDATION
# ------------------------------------------------------------------------------

PRE_ORDER_NARRATIVE = """
⬜ RESEARCH APPROVAL CAN BECOME STALE BEFORE EXECUTION

The market can change between recommendation and order submission.

The portfolio can change.

A kill switch can activate.

An option spread can widen.

An approval can expire.

A contract can become invalid.

Pre-order validation therefore rechecks the current executable state.

It does not rerun every research step.

It confirms that the approved action remains valid now.
"""


PRE_ORDER_VALIDATION_SEQUENCE = (
    "Reload current market and broker state.",
    "Confirm the configuration snapshot is still valid.",
    "Confirm no kill switch has been activated.",
    "Confirm the signal has not expired.",
    "Confirm the instrument remains eligible.",
    "Confirm the order size.",
    "Confirm portfolio limits.",
    "Confirm liquidity.",
    "Confirm options contract details.",
    "Confirm the required approval.",
    "Generate the final immutable order packet.",
    "Send the packet to the execution gateway.",
)


# ------------------------------------------------------------------------------
# 23.7 END-OF-DAY
# ------------------------------------------------------------------------------

END_OF_DAY_NARRATIVE = """
⬜ THE DECISION DOES NOT END WHEN THE ORDER IS SENT

Execution creates additional evidence.

The system must reconcile:

    - What it attempted.
    - What the broker accepted.
    - What filled.
    - At what price.
    - What position now exists.
    - What risk changed.
    - Whether the audit record is complete.

End-of-day review also identifies operational degradation before the next
session.
"""


END_OF_DAY_SEQUENCE = (
    "Reconcile orders.",
    "Reconcile fills.",
    "Reconcile positions.",
    "Capture broker rejections.",
    "Capture source failures.",
    "Capture model warnings.",
    "Archive decision records.",
    "Verify audit-log integrity.",
    "Generate unresolved-issue reports.",
    "Review kill-switch conditions.",
    "Review data-quality trends.",
    "Record the active configuration bundle.",
)


# ------------------------------------------------------------------------------
# 23.8 ILLUSTRATIVE END-TO-END DECISION FLOW
# ------------------------------------------------------------------------------

def edge_tf_decision_cycle(trade_hypothesis):
    """
    Illustrative pseudo-workflow.

    This function is intentionally descriptive rather than executable.
    """

    # 🟦 Load one validated and frozen operating constitution.
    snapshot = load_registry(
        config_path="config/",
        profile="production",
        as_of="DECISION_TIME",
    )

    # 🟦 Collect and validate only approved disclosure sources.
    disclosures = "collect_verified_disclosures(snapshot.sources)"

    # 🟥 Stop if critical source or timestamp integrity fails.
    if disclosures == "CRITICAL_FAILURE":
        return "NO_TRADE"

    # 🟦 Normalize holdings and preserve source provenance.
    normalized_holdings = "normalize(disclosures)"

    # 🟦 Map funds and securities into strategy-first functions.
    classified_evidence = "classify(normalized_holdings, snapshot.ontology)"

    # 🟦 Calculate ownership change and adoption velocity.
    signal = "score_iav(classified_evidence, snapshot.model_policy)"

    # 🟨 Search for alternative explanations.
    validated_signal = "falsify_and_validate(signal)"

    # 🟦 Compare available implementation structures.
    trade_designs = "design_trade_alternatives(validated_signal)"

    # 🟥 Apply deterministic governance and allow NO_TRADE.
    governed_action = "apply_governance(trade_designs)"

    if governed_action in ("HARD_VETO", "NO_TRADE"):
        return "NO_TRADE"

    # 🟧 Require the correct human approval tier.
    approved_action = "obtain_required_approval(governed_action)"

    if approved_action != "APPROVED":
        return "NO_TRADE"

    # 🟥 Revalidate current state immediately before execution.
    order_packet = "deterministic_pre_order_validation(approved_action)"

    if order_packet == "INVALID":
        return "NO_TRADE"

    # 🟩 Only the execution gateway may communicate with the broker.
    return "execution_gateway.submit(order_packet)"


# ==============================================================================
# 24. FAILURE HANDLING
# ==============================================================================

FAILURE_HANDLING_NARRATIVE = """
⬜ FAILURE BEHAVIOR SHOULD BE BORING AND PREDICTABLE

The worst time to invent a policy is during an outage.

Every expected failure mode should have a predefined response.

The response should state whether the system:

    - Retries.
    - Uses an approved fallback.
    - Reduces confidence.
    - Quarantines data.
    - Blocks a strategy.
    - Blocks an instrument.
    - Blocks all execution.
    - Escalates to a human.
    - Activates a kill switch.

The default production response to uncertainty in a critical control is to
stop the affected action.
"""


FAILURE_HANDLING = {
    "Issuer source unavailable": (
        "Mark source unavailable, use only an approved fallback, otherwise "
        "fail closed."
    ),
    "Unexpected file format": (
        "Quarantine source and block affected scoring."
    ),
    "Partial parse": (
        "Quarantine the entire affected artifact unless partial use is "
        "explicitly authorized."
    ),
    "Holdings fail weight tolerance": (
        "Quarantine and investigate."
    ),
    "Unknown artifact type": (
        "Fail closed."
    ),
    "Late disclosure": (
        "Record lateness and enforce decision-cutoff rules."
    ),
    "Corrected disclosure": (
        "Store a new revision; do not overwrite the original."
    ),
    "Ticker conflict": (
        "Block affected security until identifier resolution."
    ),
    "Corporate action unresolved": (
        "Block affected deltas and signals."
    ),
    "Missing ontology mapping": (
        "Exclude from function aggregation and escalate for review."
    ),
    "Missing manager mapping": (
        "Do not assume independence."
    ),
    "Market data stale": (
        "Block trade design or execution as required by policy."
    ),
    "Options data stale": (
        "Block options implementation."
    ),
    "Broker unavailable": (
        "Block live execution."
    ),
    "Broker order rejection": (
        "Record rejection and require deterministic revalidation before "
        "resubmission."
    ),
    "Governance service unavailable": (
        "Block production execution."
    ),
    "Audit service unavailable": (
        "Block production execution."
    ),
    "Configuration hash mismatch": (
        "Abort startup or activate kill switch."
    ),
}


FAILURE_ESCALATION_RECORD = {
    "incident_id": "incident_uuid",
    "detected_at": "ISO_8601_TIMESTAMP",
    "component": "source_ingestion",
    "failure_code": "FORMAT_CHANGED",
    "severity": "critical",
    "scope": [
        "fund_us_000042",
    ],
    "automatic_action": "QUARANTINE_AND_BLOCK_SIGNAL",
    "human_owner": "data_governance",
    "status": "open",
}


# ==============================================================================
# 25. SECURITY AND SECRETS
# ==============================================================================

SECURITY_NARRATIVE = """
⬜ CONFIGURATION SHOULD BE SHAREABLE WITHOUT EXPOSING CONTROL OF ACCOUNTS

The registry contains policy.

It should not contain the credentials required to move money.

Secrets belong in a dedicated secret-management system with:

    - Access control.
    - Rotation.
    - Audit logging.
    - Environment isolation.
    - Revocation.
    - Redaction.

Configuration may reference an alias.

The runtime retrieves the value only when authorized.

Agents should not receive secrets in prompts.
"""


PROHIBITED_CONFIGURATION_SECRETS = (
    "Broker usernames.",
    "Broker passwords.",
    "API keys.",
    "Private certificates.",
    "Account numbers.",
    "Bank details.",
    "Tax identifiers.",
    "Authentication tokens.",
    "Encryption keys.",
    "Personally identifiable information.",
    "Proprietary licensed-data credentials.",
)


SECRET_MANAGEMENT_POLICY = """
Secrets MUST be supplied through the approved runtime secret-management layer.

Configuration files MAY reference secret aliases.

They MUST NOT contain the secret value.

Logs MUST redact secrets and sensitive financial identifiers.
"""


SECRET_ALIAS_EXAMPLE = {
    "broker_secret_alias": "secrets/edge_tf/prod/broker_primary",
}


# ==============================================================================
# 26. REPOSITORY AND RUNTIME BOUNDARIES
# ==============================================================================

BOUNDARY_NARRATIVE = """
⬜ EACH DATA CLASS HAS A DIFFERENT LIFECYCLE

Mixing configuration, source files, features, models, prompts, audit records,
and secrets in one directory would blur authority and retention rules.

The repository boundary clarifies:

    CONFIGURATION
        Reviewed declarations that define behavior.

    RAW DATA
        Immutable external evidence.

    WAREHOUSE
        Normalized historical observations.

    FEATURE STORE
        Time-varying derived metrics.

    MODELS
        Approved executable artifacts.

    PROMPTS
        Versioned agent instructions.

    AUDIT
        Append-only decision and execution history.

    SECRETS
        External protected values.

This separation supports testing, permissions, retention, and historical
reconstruction.
"""


REPOSITORY_AND_RUNTIME_BOUNDARIES = {
    "config/": (
        "Stable, reviewed, versioned policy and registry declarations."
    ),
    "raw_data/": (
        "Immutable source artifacts."
    ),
    "warehouse/": (
        "Normalized historical observations."
    ),
    "feature_store/": (
        "Time-varying derived metrics and model features."
    ),
    "models/": (
        "Approved executable model artifacts."
    ),
    "prompts/": (
        "Versioned agent prompts."
    ),
    "audit/": (
        "Append-only decisions, approvals, and execution records."
    ),
    "secrets/": (
        "External secret manager only; never committed to the repository."
    ),
}


CONFIGURATION_STATE_POLICY = """
Configuration describes behavior.

It does not store live state.
"""


# ==============================================================================
# 27. RESPONSIBLE USE
# ==============================================================================

RESPONSIBLE_USE_NARRATIVE = """
⬜ WHAT THE SYSTEM CAN AND CANNOT CLAIM

EDGE-TF can improve the organization of research.

It can:

    - Preserve evidence.
    - Compare disclosures.
    - Detect patterns.
    - Score adoption.
    - Test consistency.
    - Generate alternatives.
    - Apply risk controls.
    - Produce an audit trail.

It cannot guarantee:

    - That institutional buying will continue.
    - That price will follow ownership.
    - That a mapping captures the full business.
    - That an option will remain liquid.
    - That a theme will outperform.
    - That a manager's purpose has been correctly inferred.
    - That a validated signal will produce profit.

The system should be confident about process and restrained about prediction.
"""


RESPONSIBLE_USE = """
EDGE-TF is a research, strategy-inference, trade-design, and governance
architecture.

It is not an autonomous oracle.

ETF disclosures provide observable evidence of portfolio behavior.

They do not reveal every reason for a manager’s decision and do not guarantee
future performance.

Institutional Adoption Velocity is a research signal.

It is not proof of causation.

Options activity may provide timing or confirmation evidence.

It may also reflect hedging, market making, spreads, or unrelated positioning.
"""


OUTPUT_RISKS = (
    "Data error.",
    "Model error.",
    "Classification error.",
    "Timing error.",
    "Market regime change.",
    "Liquidity risk.",
    "Volatility risk.",
    "Execution risk.",
    "Loss of capital.",
)


RESPONSIBLE_USE_CONCLUSION = """
No model score, agent recommendation, or disclosure pattern guarantees profit.

`NO_TRADE` is a valid and often preferable result.
"""


# ==============================================================================
# 28. GLOSSARY
# ==============================================================================

GLOSSARY_NARRATIVE = """
⬜ WHY TERMS ARE DEFINED HERE

The system combines language from:

    - ETF operations.
    - Portfolio construction.
    - Market data.
    - Ontology engineering.
    - Quantitative research.
    - Options.
    - Software governance.
    - Agent architecture.

The same word can carry different meanings across those domains.

The glossary gives EDGE-TF-specific working definitions.

Machine-readable versions of controlled vocabulary should also exist in the
relevant schemas and enum declarations.
"""


GLOSSARY = {
    "Active Ownership": (
        "Ownership resulting from discretionary portfolio-management decisions "
        "rather than purely mechanical benchmark inclusion."
    ),

    "Adoption Stage": (
        "The system’s classification of a security or business function as "
        "Absent, Seeded, Emerging, Confirmed, Consensus, Saturated, or "
        "Distribution."
    ),

    "Artifact Type": (
        "The actual disclosure object being ingested, such as full holdings, "
        "a creation basket, or a tracking basket."
    ),

    "Configuration Bundle": (
        "The complete set of versioned configuration files identified by a "
        "single manifest and bundle hash."
    ),

    "Cross-Manager Confirmation": (
        "Evidence that sufficiently independent managers are adopting the same "
        "security or business function."
    ),

    "Decision Cutoff": (
        "The latest time at which information may become available and still "
        "be used in a particular decision."
    ),

    "Distribution": (
        "An adoption stage characterized by reductions, exits, declining "
        "breadth, or weakening institutional participation."
    ),

    "Full Holdings": (
        "A verified disclosure representing the complete portfolio holdings "
        "required for the intended analysis."
    ),

    "Hard Veto": (
        "A deterministic policy condition that prohibits further action."
    ),

    "Institutional Adoption Velocity": (
        "A measure of the speed and breadth with which relevant institutional "
        "portfolios are adopting a security or business function."
    ),

    "Manager Cluster": (
        "A relationship group connecting funds through issuer, adviser, "
        "portfolio team, index methodology, corporate parent, or another "
        "common decision process."
    ),

    "Mandate Relevance": (
        "The degree to which a fund’s stated investment mandate maps to an "
        "ontology theme or business function."
    ),

    "Observed Holdings Purity": (
        "The proportion of current economic exposure attributable to eligible "
        "ontology functions."
    ),

    "Ontology": (
        "The structured hierarchy used to map themes, business functions, "
        "companies, securities, and strategic roles."
    ),

    "Ownership Consensus": (
        "A mature state in which a security or strategy is already broadly "
        "represented across institutional portfolios."
    ),

    "Ownership Formation": (
        "A developing state in which institutional breadth, shares, or "
        "thematic participation is increasing."
    ),

    "Point-in-Time Integrity": (
        "The requirement that a decision use only information demonstrably "
        "available before the decision cutoff."
    ),

    "Price-Driven Weight Drift": (
        "A portfolio-weight change caused primarily by market-price movement "
        "rather than manager share accumulation."
    ),

    "Quarantine": (
        "The isolation of invalid, incomplete, stale, or unresolved data from "
        "scoring and execution."
    ),

    "Signal Source": (
        "A fund or disclosure source eligible to contribute evidence to "
        "strategy inference."
    ),

    "Soft Penalty": (
        "A condition that reduces score, confidence, permissible size, or "
        "implementation priority without automatically prohibiting action."
    ),

    "Strategy-First Ontology": (
        "The classification system that begins with the strategic business "
        "function rather than the ticker."
    ),

    "Strategic Diffusion": (
        "The spread of a business function across specialist, thematic, broad "
        "active, or benchmark portfolios."
    ),

    "System Role": (
        "The permitted use of a fund inside EDGE-TF, such as signal source, "
        "control, implementation candidate, or hedge candidate."
    ),
}


# ==============================================================================
# 29. PRODUCTION PROMOTION CHECKLIST
# ==============================================================================

PROMOTION_CHECKLIST_NARRATIVE = """
⬜ THE CHECKLIST IS A RELEASE GATE, NOT A SUGGESTION

The production checklist should be implemented in automation wherever
possible.

A checked box should correspond to evidence.

Examples:

    - A passing CI job.
    - A generated hash.
    - A signed approval record.
    - A successful replay test.
    - A completed shadow period.
    - A secret scan.
    - A verified rollback bundle.

The final promotion decision should link to those artifacts.
"""


PRODUCTION_PROMOTION_CHECKLIST = (
    "[ ] All files in the directory manifest exist.",
    "[ ] All JSON files parse successfully.",
    "[ ] All JSON files pass schema validation.",
    "[ ] Every file has a generated SHA-256 hash.",
    "[ ] The manifest contains the correct active fund count.",
    "[ ] Every fund has a stable internal identifier.",
    "[ ] Every signal-eligible fund has a verified complete-holdings source.",
    "[ ] Disclosure artifact types have been verified.",
    "[ ] Manager clusters have been populated.",
    "[ ] Ontology mappings have been reviewed.",
    "[ ] Model weights and thresholds exist in `model_policy.json`.",
    "[ ] Hard risk limits exist in `governance_policy.json`.",
    "[ ] Research, paper, and production profiles pass validation.",
    "[ ] Profile overrides cannot loosen base governance.",
    "[ ] Point-in-time replay tests pass.",
    "[ ] Historical regression tests pass.",
    "[ ] Corporate-action handling tests pass.",
    "[ ] Missing-data tests pass.",
    "[ ] Kill-switch tests pass.",
    "[ ] Agent permission tests pass.",
    "[ ] Deterministic pre-order validation tests pass.",
    "[ ] Audit-log integrity tests pass.",
    "[ ] No secrets are present in the repository.",
    "[ ] Required governance approvals have been recorded.",
    "[ ] A verified rollback target has been recorded.",
    "[ ] The release bundle has been signed.",
    "[ ] The production deployment has completed a paper or shadow observation "
    "period.",
)


# ==============================================================================
# 30. FINAL GOVERNING RULE
# ==============================================================================

FINAL_GOVERNING_RULE_NARRATIVE = """
⬜ THE SYSTEM'S CENTRAL DISCIPLINE

The purpose of EDGE-TF is not to replace judgment with automation.

The purpose is to prevent judgment from becoming:

    - Unstructured.
    - Unverifiable.
    - Inconsistent.
    - Unbounded.
    - Irreproducible.

The system should make a strong research idea easier to examine.

It should make a weak research idea easier to reject.

It should make risk limits harder to bypass.

It should make every production decision easier to reconstruct.

The architecture succeeds when it improves the quality of the questions before
it accelerates the speed of the answers.
"""


FINAL_GOVERNING_RULE = """
EDGE-TF may accelerate collection, comparison, classification, scoring, and
trade design.

It may not eliminate uncertainty.

The architecture is designed to make uncertainty visible, measurable,
reviewable, and governable.
"""


FINAL_OPERATING_SEQUENCE = (
    "Evidence before inference.",
    "Inference before implementation.",
    "Disconfirmation before capital.",
    "Governance before execution.",
    "Audit before trust.",
)


FINAL_SYSTEM_ASSERTIONS = {
    "evidence_before_inference": True,
    "human_accountability_retained": True,
    "hard_vetoes_are_deterministic": True,
    "agents_cannot_self_authorize": True,
    "no_trade_is_valid": True,
    "released_bundles_are_reproducible": True,
    "unknown_critical_data_fails_closed": True,
    "every_execution_requires_auditability": True,
}


# ==============================================================================
# END OF EDGE-TF™ CONFIGURATION AND POLICY REGISTRY
# ==============================================================================
#
# FINAL REMINDER:
#
#     Read the fund before the ticker.
#     Read shares before weight.
#     Read category before company.
#     Read persistence before excitement.
#     Read disconfirmation before implementation.
#
# ==============================================================================
```
