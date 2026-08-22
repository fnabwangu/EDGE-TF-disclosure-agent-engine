"""
Portfolio state store for the external execution boundary.

Path: execution/portfolio.py

The execution service is the source of truth for broker balances and fills;
this store is EDGE-TF's append-only mirror of everything it has reported.
Snapshots and reports are persisted as JSONL so the state survives restarts
and stays independently auditable, in the same spirit as the workbench log
and the decision records.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from execution.contracts import BrokerAccountSnapshot, ExecutionReport

DEFAULT_DIR = Path("data/portfolio")


class PortfolioStateStore:
    """Append-only ledger of broker snapshots and execution reports."""

    def __init__(self, store_dir: Path | str = DEFAULT_DIR):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._snapshots_path = self.store_dir / "snapshots.jsonl"
        self._reports_path = self.store_dir / "execution_reports.jsonl"
        self._snapshots: List[BrokerAccountSnapshot] = []
        self._reports: List[ExecutionReport] = []
        self._load()

    # -- writes ------------------------------------------------------------

    def record_snapshot(self, snapshot: BrokerAccountSnapshot) -> BrokerAccountSnapshot:
        self._snapshots.append(snapshot)
        self._append(self._snapshots_path, snapshot.model_dump(mode="json"))
        return snapshot

    def record_report(self, report: ExecutionReport) -> ExecutionReport:
        self._reports.append(report)
        self._append(self._reports_path, report.model_dump(mode="json"))
        return report

    # -- reads -------------------------------------------------------------

    def latest_snapshot(self, *, broker: Optional[str] = None) -> Optional[BrokerAccountSnapshot]:
        for snapshot in reversed(self._snapshots):
            if broker is None or snapshot.broker == broker:
                return snapshot
        return None

    def snapshots(self) -> List[BrokerAccountSnapshot]:
        return list(self._snapshots)

    def reports(self, *, trade_id: Optional[str] = None) -> List[ExecutionReport]:
        return [r for r in self._reports if trade_id is None or r.trade_id == trade_id]

    def positions_by_broker(self) -> Dict[str, Dict[str, float]]:
        """Most recent net quantity per symbol per broker."""
        latest: Dict[str, BrokerAccountSnapshot] = {}
        for snapshot in self._snapshots:
            latest[snapshot.broker] = snapshot
        return {
            broker: {p.symbol: p.quantity for p in snap.positions}
            for broker, snap in latest.items()
        }

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _append(path: Path, payload: Dict) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")

    def _load(self) -> None:
        if self._snapshots_path.exists():
            for line in self._snapshots_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._snapshots.append(BrokerAccountSnapshot.model_validate_json(line))
        if self._reports_path.exists():
            for line in self._reports_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._reports.append(ExecutionReport.model_validate_json(line))


__all__ = ["DEFAULT_DIR", "PortfolioStateStore"]
