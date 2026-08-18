from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_product_imports_use_root_authorities():
    source_files = [
        ROOT / "tests" / "test_quant_engine.py",
        ROOT / "tests" / "test_fail_closed_controls.py",
        ROOT / "tests" / "test_audit_failure_modes.py",
        ROOT / "audit" / "regression_audit_replay.py",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        assert "from src" not in text
        assert "import src" not in text


def test_migrated_src_modules_are_shims_not_implementations():
    shim_files = {
        "src/quant_engine/manager_graph.py": "ManagerGraphEngine",
        "src/ingestion/normalizer.py": "DisclosureNormalizer",
        "src/governance/risk_governor.py": "RiskGovernor",
        "src/inference/hypothesis_agent.py": "HypothesisAgent",
        "src/trade_design/options_modeler.py": "BlackScholesEngine",
    }
    for relative_path, implementation_name in shim_files.items():
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert f"class {implementation_name}" not in text
        assert "Legacy" in text
