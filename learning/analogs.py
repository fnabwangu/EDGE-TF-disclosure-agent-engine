"""
Historical analog and trade retrieval engine.

Path: learning/analogs.py

Retrieves historically similar events and trade implementations to provide
interpretable evidence for current thesis scoring and implementation selection.

Finds analogs before ML prediction so models work on grounded evidence.
"""

import math
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
from dataclasses import dataclass

from learning.schemas import (
    SetupFingerprint,
    HistoricalEvent,
    HistoricalTrade,
    AnalogMatch,
    AnalogSet,
)


class SetupEncoder:
    """
    Encodes trade setups as structured fingerprints for similarity matching.
    """
    
    def encode_setup(
        self,
        event_type: str,
        region: Optional[str] = None,
        asset_class: Optional[str] = None,
        commodity: Optional[str] = None,
        policy_mechanism: Optional[str] = None,
        supply_impact: Optional[str] = None,
        shipping_impact: Optional[str] = None,
        financial_enforcement: Optional[str] = None,
        demand_impact: Optional[str] = None,
        market_regime: Optional[str] = None,
        volatility_regime: Optional[str] = None,
        liquidity_regime: Optional[str] = None,
        macro_backdrop: Optional[str] = None,
        custom_features: Optional[Dict] = None,
    ) -> SetupFingerprint:
        """Create structured fingerprint from setup description."""
        return SetupFingerprint(
            event_type=event_type,
            region=region,
            asset_class=asset_class,
            commodity=commodity,
            policy_mechanism=policy_mechanism,
            supply_impact=supply_impact,
            shipping_impact=shipping_impact,
            financial_enforcement=financial_enforcement,
            demand_impact=demand_impact,
            market_regime=market_regime,
            volatility_regime=volatility_regime,
            liquidity_regime=liquidity_regime,
            macro_backdrop=macro_backdrop,
            custom_features=custom_features or {},
        )


class SimilarityCalculator:
    """
    Computes similarity between setup fingerprints.
    
    Uses weighted component matching:
    - Exact categorical matches (event type, region, commodity)
    - Scalar matches (supply impact, volatility regime)
    - Custom features
    """
    
    def __init__(self):
        # Weights for different components [0, 1]
        self.component_weights = {
            "event_type": 0.30,
            "region": 0.10,
            "commodity": 0.10,
            "supply_impact": 0.15,
            "shipping_impact": 0.10,
            "policy_mechanism": 0.10,
            "market_regime": 0.05,
            "volatility_regime": 0.05,
            "macro_backdrop": 0.05,
        }
    
    def similarity(
        self,
        current: SetupFingerprint,
        historical: SetupFingerprint,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Compute similarity score [0, 1] and component breakdown.
        
        Returns:
            (overall_similarity, component_scores)
        """
        components: Dict[str, float] = {}
        weighted_sum = 0.0
        
        # Event type (categorical)
        components["event_type"] = (
            1.0 if current.event_type == historical.event_type else 0.0
        )
        weighted_sum += components["event_type"] * self.component_weights["event_type"]
        
        # Region (categorical)
        components["region"] = (
            1.0 if current.region == historical.region else 0.5
        ) if current.region and historical.region else 0.5
        weighted_sum += components["region"] * self.component_weights["region"]
        
        # Commodity (categorical)
        components["commodity"] = (
            1.0 if current.commodity == historical.commodity else 0.5
        ) if current.commodity and historical.commodity else 0.5
        weighted_sum += components["commodity"] * self.component_weights["commodity"]
        
        # Supply impact (scalar)
        components["supply_impact"] = self._scalar_similarity(
            current.supply_impact,
            historical.supply_impact,
        )
        weighted_sum += components["supply_impact"] * self.component_weights["supply_impact"]
        
        # Shipping impact
        components["shipping_impact"] = self._scalar_similarity(
            current.shipping_impact,
            historical.shipping_impact,
        )
        weighted_sum += components["shipping_impact"] * self.component_weights["shipping_impact"]
        
        # Policy mechanism
        components["policy_mechanism"] = (
            1.0 if current.policy_mechanism == historical.policy_mechanism else 0.5
        ) if current.policy_mechanism and historical.policy_mechanism else 0.5
        weighted_sum += components["policy_mechanism"] * self.component_weights["policy_mechanism"]
        
        # Market regime
        components["market_regime"] = (
            1.0 if current.market_regime == historical.market_regime else 0.3
        ) if current.market_regime and historical.market_regime else 0.3
        weighted_sum += components["market_regime"] * self.component_weights["market_regime"]
        
        # Volatility regime
        components["volatility_regime"] = (
            1.0 if current.volatility_regime == historical.volatility_regime else 0.3
        ) if current.volatility_regime and historical.volatility_regime else 0.3
        weighted_sum += components["volatility_regime"] * self.component_weights["volatility_regime"]
        
        # Macro backdrop
        components["macro_backdrop"] = (
            1.0 if current.macro_backdrop == historical.macro_backdrop else 0.2
        ) if current.macro_backdrop and historical.macro_backdrop else 0.2
        weighted_sum += components["macro_backdrop"] * self.component_weights["macro_backdrop"]
        
        return weighted_sum, components
    
    def _scalar_similarity(self, current: Optional[str], historical: Optional[str]) -> float:
        """Match scalar levels: high/medium/low."""
        if not current or not historical:
            return 0.5
        if current == historical:
            return 1.0
        # Adjacent levels get partial credit
        if (current, historical) in [("high", "medium"), ("medium", "high"),
                                     ("medium", "low"), ("low", "medium")]:
            return 0.7
        return 0.0


class EventRetriever:
    """
    Retrieves historically similar events.
    """
    
    def __init__(self):
        self.events: List[HistoricalEvent] = []
        self.calculator = SimilarityCalculator()
    
    def add_event(self, event: HistoricalEvent) -> None:
        """Register a historical event."""
        self.events.append(event)
    
    def find_similar_events(
        self,
        fingerprint: SetupFingerprint,
        top_k: int = 5,
        min_similarity: float = 0.50,
    ) -> List[AnalogMatch]:
        """
        Find most similar historical events.
        
        Returns:
            List of AnalogMatch sorted by similarity (descending).
        """
        matches: List[Tuple[HistoricalEvent, float, Dict[str, float]]] = []
        
        for event in self.events:
            similarity, components = self.calculator.similarity(
                fingerprint,
                event.fingerprint,
            )
            
            if similarity >= min_similarity:
                matches.append((event, similarity, components))
        
        # Sort by similarity descending
        matches.sort(key=lambda x: x[1], reverse=True)
        
        # Convert to AnalogMatch objects
        result: List[AnalogMatch] = []
        for event, similarity, components in matches[:top_k]:
            match = AnalogMatch(
                current_setup_id="current",  # Placeholder
                analog_event_id=event.event_id,
                similarity_score=similarity,
                similarity_components=components,
                match_quality=self._classify_quality(similarity),
            )
            result.append(match)
        
        return result
    
    def _classify_quality(self, similarity: float) -> str:
        if similarity >= 0.80:
            return "high"
        elif similarity >= 0.65:
            return "medium"
        else:
            return "low"


class TradeRetriever:
    """
    Retrieves historically similar trade implementations.
    """
    
    def __init__(self):
        self.trades: List[HistoricalTrade] = []
    
    def add_trade(self, trade: HistoricalTrade) -> None:
        """Register a historical trade."""
        self.trades.append(trade)
    
    def find_similar_implementations(
        self,
        implementation_type: str,
        top_k: int = 5,
    ) -> List[AnalogMatch]:
        """
        Find trades with similar implementation approach.
        
        Returns:
            List of AnalogMatch sorted by similarity.
        """
        matches: List[Tuple[HistoricalTrade, float]] = []
        
        for trade in self.trades:
            # Exact type match gets full credit
            similarity = 1.0 if trade.implementation_type == implementation_type else 0.5
            
            if trade.return_realized is not None and trade.return_realized > 0:
                similarity *= 1.1  # Successful trades weighted higher
            
            matches.append((trade, similarity))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        
        result: List[AnalogMatch] = []
        for trade, similarity, in matches[:top_k]:
            match = AnalogMatch(
                current_setup_id="current",
                analog_event_id=trade.trade_id,
                similarity_score=similarity,
                match_quality="high" if similarity > 0.8 else "medium",
            )
            result.append(match)
        
        return result


class AnalogRanker:
    """
    Synthesizes and ranks analog sets for presentation.
    """
    
    def rank_analogs(
        self,
        event_matches: List[AnalogMatch],
        events: Dict[str, HistoricalEvent],
        trade_matches: List[AnalogMatch],
        trades: Dict[str, HistoricalTrade],
    ) -> Dict[str, any]:
        """
        Create ranked summary of best analogs.
        
        Returns:
            Structured summary with patterns, recommendations, etc.
        """
        summary = {
            "top_event_analogs": [],
            "top_trade_analogs": [],
            "observed_patterns": [],
            "key_findings": [],
            "recommendations": [],
        }
        
        # Process event analogs
        for match in event_matches[:3]:
            event = events.get(match.analog_event_id)
            if event:
                summary["top_event_analogs"].append({
                    "event_id": event.event_id,
                    "event_date": event.event_date.isoformat(),
                    "similarity": match.similarity_score,
                    "return_5d": event.return_5d,
                    "return_20d": event.return_20d,
                    "return_60d": event.return_60d,
                    "best_implementation": event.best_implementation,
                    "description": event.description,
                })
        
        # Process trade analogs
        for match in trade_matches[:3]:
            trade = trades.get(match.analog_event_id)
            if trade:
                summary["top_trade_analogs"].append({
                    "trade_id": trade.trade_id,
                    "implementation": trade.implementation_type,
                    "return": trade.return_realized,
                    "max_drawdown": trade.max_drawdown,
                    "hedge_effectiveness": trade.hedge_effectiveness,
                    "outcome": trade.outcome,
                })
        
        # Extract patterns
        if event_matches:
            patterns = self._extract_patterns(
                [events.get(m.analog_event_id) for m in event_matches]
            )
            summary["observed_patterns"] = patterns
        
        return summary
    
    def _extract_patterns(self, events: List[Optional[HistoricalEvent]]) -> List[str]:
        """Extract common patterns from matched events."""
        patterns = []
        
        # Filter out None
        valid_events = [e for e in events if e]
        
        if not valid_events:
            return patterns
        
        # Check for commodity performance patterns
        commodity_returns = [e.commodity_return for e in valid_events if e.commodity_return]
        producer_returns = [e.producer_equity_return for e in valid_events if e.producer_equity_return]
        
        if producer_returns and commodity_returns:
            avg_producer = sum(producer_returns) / len(producer_returns)
            avg_commodity = sum(commodity_returns) / len(commodity_returns)
            
            if avg_producer > avg_commodity:
                patterns.append("Producer equities historically outperformed direct commodity exposure")
            else:
                patterns.append("Direct commodity exposure historically outperformed producer equities")
        
        # Check for rerouting vs supply loss
        supply_impacts = [e.oil_supply_impact for e in valid_events if e.oil_supply_impact]
        if supply_impacts and all(0 < s < 0.2 for s in supply_impacts):
            patterns.append("Supply disruptions were primarily rerouting, not permanent supply loss")
        
        return patterns


class OutcomeSummary:
    """
    Summarizes outcomes from historical analogs.
    """
    
    def summarize_analog_outcomes(
        self,
        events: List[HistoricalEvent],
    ) -> Dict[str, any]:
        """Compute outcome statistics from analog events."""
        if not events:
            return {}
        
        returns_5d = [e.return_5d for e in events if e.return_5d]
        returns_20d = [e.return_20d for e in events if e.return_20d]
        returns_60d = [e.return_60d for e in events if e.return_60d]
        
        summary = {}
        
        if returns_5d:
            summary["return_5d_avg"] = sum(returns_5d) / len(returns_5d)
            summary["return_5d_min"] = min(returns_5d)
            summary["return_5d_max"] = max(returns_5d)
        
        if returns_20d:
            summary["return_20d_avg"] = sum(returns_20d) / len(returns_20d)
            summary["return_20d_min"] = min(returns_20d)
            summary["return_20d_max"] = max(returns_20d)
        
        if returns_60d:
            summary["return_60d_avg"] = sum(returns_60d) / len(returns_60d)
            summary["return_60d_min"] = min(returns_60d)
            summary["return_60d_max"] = max(returns_60d)
        
        return summary


class AnalogEngine:
    """
    Complete analog retrieval and synthesis engine.
    
    Coordinates event retrieval, trade retrieval, ranking, and summarization.
    """
    
    def __init__(self):
        self.encoder = SetupEncoder()
        self.event_retriever = EventRetriever()
        self.trade_retriever = TradeRetriever()
        self.ranker = AnalogRanker()
        self.outcome_summary = OutcomeSummary()
        
        self.event_lookup: Dict[str, HistoricalEvent] = {}
        self.trade_lookup: Dict[str, HistoricalTrade] = {}
    
    def register_historical_event(self, event: HistoricalEvent) -> None:
        """Register event in engine."""
        self.event_retriever.add_event(event)
        self.event_lookup[event.event_id] = event
    
    def register_historical_trade(self, trade: HistoricalTrade) -> None:
        """Register trade in engine."""
        self.trade_retriever.add_trade(trade)
        self.trade_lookup[trade.trade_id] = trade
    
    def add_event(self, event: HistoricalEvent) -> None:
        """Register a historical event."""
        self.register_historical_event(event)
    
    def add_trade(self, trade: HistoricalTrade) -> None:
        """Register a historical trade."""
        self.register_historical_trade(trade)
    
    def find_analogs(
        self,
        current_setup: SetupFingerprint,
        implementation_type: str,
        min_event_similarity: float = 0.50,
        top_k: int = 5,
    ) -> AnalogSet:
        """
        Find and rank analogs for a setup.
        
        Returns:
            Complete AnalogSet with event and trade matches.
        """
        # Find event analogs
        event_matches = self.event_retriever.find_similar_events(
            current_setup,
            top_k=top_k,
            min_similarity=min_event_similarity,
        )
        
        # Find trade analogs
        trade_matches = self.trade_retriever.find_similar_implementations(
            implementation_type,
            top_k=top_k,
        )
        
        # Rank and summarize
        ranking = self.ranker.rank_analogs(
            event_matches,
            self.event_lookup,
            trade_matches,
            self.trade_lookup,
        )
        
        # Outcome statistics
        matched_events = [self.event_lookup.get(m.analog_event_id) for m in event_matches]
        matched_events = [e for e in matched_events if e]
        outcome_stats = self.outcome_summary.summarize_analog_outcomes(matched_events)
        
        # Confidence level
        confidence = "no_analog"
        if event_matches:
            if max(m.similarity_score for m in event_matches) >= 0.80:
                confidence = "high"
            elif max(m.similarity_score for m in event_matches) >= 0.65:
                confidence = "medium"
            else:
                confidence = "low"
        
        return AnalogSet(
            setup_id="current_setup",
            current_fingerprint=current_setup,
            timestamp=datetime.utcnow(),
            event_analogs=event_matches,
            trade_analogs=trade_matches,
            outcome_statistics=outcome_stats,
            observed_patterns=ranking.get("observed_patterns", []),
            confidence_level=confidence,
            minimum_similarity_threshold=min_event_similarity,
        )
    
    def retrieve_analogs(
        self,
        fingerprint: SetupFingerprint,
        top_k: int = 5,
        min_similarity: float = 0.50,
        implementation_type: str = "generic",
    ) -> AnalogSet:
        """
        Retrieve analogs with standard parameters.
        
        This is the main method for analog retrieval during decision making.
        """
        return self.find_analogs(
            current_setup=fingerprint,
            implementation_type=implementation_type,
            min_event_similarity=min_similarity,
            top_k=top_k,
        )
