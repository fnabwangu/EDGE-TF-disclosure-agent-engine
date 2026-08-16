"""audit_logger.py
Simple decision record logger that writes JSON to data/decision_records.
"""
import json
from pathlib import Path

def log_decision(record: dict, out_dir: str = "data/decision_records"):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    idx = len(list(Path(out_dir).glob("*.json")))
    path = Path(out_dir) / f"decision_{idx+1}.json"
    path.write_text(json.dumps(record, indent=2))
    return str(path)
