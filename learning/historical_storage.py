"""
Historical event and trade storage and retrieval.

Path: learning/historical_storage.py

Persistent storage for:
- Historical events (geopolitical, macro, supply shocks, etc.)
- Historical trade implementations and outcomes
- Outcome statistics and performance data

This enables analog retrieval and pattern learning.
"""

from datetime import date, datetime, timezone
from typing import Dict, List, Optional
from pathlib import Path
import json

from learning.schemas import HistoricalEvent, HistoricalTrade


class HistoricalEventStore:
    """
    Persistent storage for historical events.
    """
    
    def __init__(self, storage_dir: Path | str = "data/historical_events"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.events: Dict[str, HistoricalEvent] = {}
        self._load_all()
    
    def _load_all(self) -> None:
        """Load all historical events from storage."""
        events_dir = self.storage_dir / "events"
        if not events_dir.exists():
            return
        
        for json_file in events_dir.glob("*.json"):
            with open(json_file) as f:
                data = json.load(f)
                event = HistoricalEvent(**data)
                self.events[event.event_id] = event
    
    def add_event(self, event: HistoricalEvent) -> None:
        """Register a new historical event."""
        self.events[event.event_id] = event
        self._save_event(event)
    
    def _save_event(self, event: HistoricalEvent) -> None:
        """Persist event to JSON."""
        events_dir = self.storage_dir / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        
        path = events_dir / f"{event.event_id}.json"
        data = event.model_dump()
        
        # Convert dates to ISO format
        for key, value in data.items():
            if isinstance(value, (date, datetime)):
                data[key] = value.isoformat()
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    def get_event(self, event_id: str) -> Optional[HistoricalEvent]:
        """Retrieve event by ID."""
        return self.events.get(event_id)
    
    def find_by_event_type(self, event_type: str) -> List[HistoricalEvent]:
        """Find all events of a specific type."""
        return [e for e in self.events.values() if e.event_type == event_type]
    
    def find_by_region(self, region: str) -> List[HistoricalEvent]:
        """Find all events in a specific region."""
        return [e for e in self.events.values() if e.region == region]
    
    def find_by_date_range(self, start: date, end: date) -> List[HistoricalEvent]:
        """Find events within a date range."""
        return [
            e for e in self.events.values()
            if start <= e.event_date <= end
        ]
    
    def list_all(self) -> List[HistoricalEvent]:
        """Get all historical events."""
        return list(self.events.values())
    
    def export_summary(self) -> Dict:
        """Export summary statistics."""
        return {
            "total_events": len(self.events),
            "date_range": {
                "earliest": min((e.event_date for e in self.events.values()), default=None).isoformat() if self.events else None,
                "latest": max((e.event_date for e in self.events.values()), default=None).isoformat() if self.events else None,
            },
            "event_types": list(set(e.event_type for e in self.events.values())),
            "regions": list(set(e.region for e in self.events.values() if e.region)),
        }


class HistoricalTradeStore:
    """
    Persistent storage for historical trade implementations and outcomes.
    """
    
    def __init__(self, storage_dir: Path | str = "data/historical_trades"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.trades: Dict[str, HistoricalTrade] = {}
        self._load_all()
    
    def _load_all(self) -> None:
        """Load all historical trades from storage."""
        trades_dir = self.storage_dir / "trades"
        if not trades_dir.exists():
            return
        
        for json_file in trades_dir.glob("*.json"):
            with open(json_file) as f:
                data = json.load(f)
                trade = HistoricalTrade(**data)
                self.trades[trade.trade_id] = trade
    
    def add_trade(self, trade: HistoricalTrade) -> None:
        """Register a new historical trade."""
        self.trades[trade.trade_id] = trade
        self._save_trade(trade)
    
    def _save_trade(self, trade: HistoricalTrade) -> None:
        """Persist trade to JSON."""
        trades_dir = self.storage_dir / "trades"
        trades_dir.mkdir(parents=True, exist_ok=True)
        
        path = trades_dir / f"{trade.trade_id}.json"
        data = trade.model_dump()
        
        # Convert dates to ISO format
        for key, value in data.items():
            if isinstance(value, (date, datetime)):
                data[key] = value.isoformat()
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    def get_trade(self, trade_id: str) -> Optional[HistoricalTrade]:
        """Retrieve trade by ID."""
        return self.trades.get(trade_id)
    
    def find_by_event(self, event_id: str) -> List[HistoricalTrade]:
        """Find all trades related to a specific event."""
        return [t for t in self.trades.values() if t.event_id == event_id]
    
    def find_by_implementation_type(self, impl_type: str) -> List[HistoricalTrade]:
        """Find trades with specific implementation type."""
        return [t for t in self.trades.values() if t.implementation_type == impl_type]
    
    def find_successful_trades(self) -> List[HistoricalTrade]:
        """Find all trades with positive return."""
        return [
            t for t in self.trades.values()
            if t.return_realized and t.return_realized > 0
        ]
    
    def find_by_date_range(self, start: date, end: date) -> List[HistoricalTrade]:
        """Find trades completed within date range."""
        return [
            t for t in self.trades.values()
            if start <= t.trade_date <= end
        ]
    
    def list_all(self) -> List[HistoricalTrade]:
        """Get all historical trades."""
        return list(self.trades.values())
    
    def export_summary(self) -> Dict:
        """Export summary statistics."""
        successful = self.find_successful_trades()
        all_returns = [t.return_realized for t in self.trades.values() if t.return_realized]
        
        return {
            "total_trades": len(self.trades),
            "successful_trades": len(successful),
            "win_rate": len(successful) / max(1, len(self.trades)),
            "average_return": sum(all_returns) / len(all_returns) if all_returns else 0.0,
            "implementation_types": list(set(t.implementation_type for t in self.trades.values())),
        }


class HistoricalPatternExtractor:
    """
    Extract patterns from historical events and trades.
    """
    
    def __init__(
        self,
        event_store: HistoricalEventStore,
        trade_store: HistoricalTradeStore,
    ):
        self.event_store = event_store
        self.trade_store = trade_store
    
    def extract_patterns_by_event_type(self, event_type: str) -> Dict:
        """Extract aggregate patterns for specific event type."""
        events = self.event_store.find_by_event_type(event_type)
        
        if not events:
            return {}
        
        # Collect outcome statistics
        returns_5d = [e.return_5d for e in events if e.return_5d]
        returns_20d = [e.return_20d for e in events if e.return_20d]
        returns_60d = [e.return_60d for e in events if e.return_60d]
        
        # Compare instrument performance
        commodity_returns = [e.commodity_return for e in events if e.commodity_return]
        producer_returns = [e.producer_equity_return for e in events if e.producer_equity_return]
        broad_returns = [e.broad_market_return for e in events if e.broad_market_return]
        
        return {
            "event_type": event_type,
            "historical_events": len(events),
            "returns_5d_avg": sum(returns_5d) / len(returns_5d) if returns_5d else None,
            "returns_20d_avg": sum(returns_20d) / len(returns_20d) if returns_20d else None,
            "returns_60d_avg": sum(returns_60d) / len(returns_60d) if returns_60d else None,
            "commodity_avg_return": sum(commodity_returns) / len(commodity_returns) if commodity_returns else None,
            "producer_avg_return": sum(producer_returns) / len(producer_returns) if producer_returns else None,
            "broad_market_avg_return": sum(broad_returns) / len(broad_returns) if broad_returns else None,
            "commodity_outperformed_producer": (
                sum(commodity_returns) / len(commodity_returns) > sum(producer_returns) / len(producer_returns)
                if commodity_returns and producer_returns else None
            ),
            "producer_outperformed_broad": (
                sum(producer_returns) / len(producer_returns) > sum(broad_returns) / len(broad_returns)
                if producer_returns and broad_returns else None
            ),
        }
    
    def extract_patterns_by_region(self, region: str) -> Dict:
        """Extract aggregate patterns for specific region."""
        events = self.event_store.find_by_region(region)
        
        if not events:
            return {}
        
        event_types = set(e.event_type for e in events)
        
        return {
            "region": region,
            "historical_events": len(events),
            "event_types_observed": list(event_types),
            "date_range_start": min(e.event_date for e in events).isoformat() if events else None,
            "date_range_end": max(e.event_date for e in events).isoformat() if events else None,
        }
    
    def extract_implementation_patterns(self, impl_type: str) -> Dict:
        """Extract patterns about specific trade implementation."""
        trades = self.trade_store.find_by_implementation_type(impl_type)
        
        if not trades:
            return {}
        
        returns = [t.return_realized for t in trades if t.return_realized]
        drawdowns = [t.max_drawdown for t in trades if t.max_drawdown]
        hedge_costs = [t.hedge_cost for t in trades if t.hedge_cost]
        
        return {
            "implementation_type": impl_type,
            "historical_trades": len(trades),
            "win_rate": sum(1 for r in returns if r > 0) / len(returns) if returns else 0.0,
            "average_return": sum(returns) / len(returns) if returns else None,
            "average_drawdown": sum(drawdowns) / len(drawdowns) if drawdowns else None,
            "average_hedge_cost": sum(hedge_costs) / len(hedge_costs) if hedge_costs else None,
        }
