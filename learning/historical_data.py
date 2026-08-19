"""
Historical data loader for analog engine.

Path: learning/historical_data.py

Loads historical events and trades into the analog engine to enable
analog retrieval during research and implementation phases.

Contains example historical events (real geopolitical episodes) for
testing and demonstrates how to populate the analog database.
"""

from datetime import date
from typing import List

from learning.schemas import (
    HistoricalEvent,
    HistoricalTrade,
    SetupFingerprint,
)
from learning.analogs import AnalogEngine


class HistoricalDataLoader:
    """Populates analog engine with historical events and trades."""
    
    def __init__(self, analog_engine: AnalogEngine):
        self.engine = analog_engine
    
    def load_oil_geopolitical_events(self) -> List[HistoricalEvent]:
        """Load historical oil geopolitical events."""
        events = [
            # 2022 Iran Nuclear Deal Escalation
            HistoricalEvent(
                event_id="hist_iran_2022_06",
                event_date=date(2022, 6, 15),
                fingerprint=SetupFingerprint(
                    event_type="secondary_sanctions",
                    region="middle_east",
                    asset_class="energy",
                    commodity="oil",
                    policy_mechanism="financial_enforcement",
                    supply_impact="medium",
                    shipping_impact="high",
                    financial_enforcement="high",
                    market_regime="risk_off",
                    volatility_regime="elevated",
                ),
                description="Iran secondary sanctions escalation following nuclear deal tensions",
                macro_regime="risk_off",
                sanctions_intensity=0.78,
                oil_supply_impact=0.14,
                freight_impact=0.22,
                financial_enforcement_intensity=0.85,
                return_5d=0.032,
                return_20d=0.087,
                return_60d=0.156,
                commodity_return=0.024,
                producer_equity_return=0.095,
                broad_market_return=-0.018,
                volatility_response=0.35,
                best_implementation="long_producer_equities_with_put_spreads",
                worst_implementation="direct_crude_futures",
                max_drawdown=-0.045,
                time_to_peak_response_days=18,
                thesis_outcome="confirmed",
                notes="Producer equities outperformed due to exploration upside. Direct crude consolidation hurt.",
            ),
            
            # 2021 Russian-Ukraine Tensions
            HistoricalEvent(
                event_id="hist_ukraine_2021_11",
                event_date=date(2021, 11, 1),
                fingerprint=SetupFingerprint(
                    event_type="geopolitical_conflict",
                    region="europe",
                    asset_class="energy",
                    commodity="oil_and_gas",
                    policy_mechanism="supply_risk",
                    supply_impact="high",
                    shipping_impact="medium",
                    financial_enforcement="low",
                    market_regime="risk_on",
                    volatility_regime="elevated",
                ),
                description="Russian military buildup near Ukraine; energy supply fears",
                macro_regime="risk_on_to_off",
                sanctions_intensity=0.0,
                oil_supply_impact=0.22,
                freight_impact=0.15,
                financial_enforcement_intensity=0.0,
                return_5d=0.028,
                return_20d=0.12,
                return_60d=0.18,
                commodity_return=0.035,
                producer_equity_return=0.11,
                broad_market_return=-0.025,
                volatility_response=0.42,
                best_implementation="diversified_energy_with_call_spreads",
                worst_implementation="isolated_xle_longs",
                max_drawdown=-0.068,
                time_to_peak_response_days=12,
                thesis_outcome="confirmed",
                notes="Supply concerns drove broad energy strength. Diversification important for drawdown control.",
            ),
            
            # 2020 OPEC+ Production Cuts
            HistoricalEvent(
                event_id="hist_opec_2020_04",
                event_date=date(2020, 4, 12),
                fingerprint=SetupFingerprint(
                    event_type="supply_reduction",
                    region="global",
                    asset_class="energy",
                    commodity="oil",
                    policy_mechanism="production_discipline",
                    supply_impact="high",
                    shipping_impact="low",
                    financial_enforcement="medium",
                    market_regime="risk_off",
                    volatility_regime="very_elevated",
                ),
                description="OPEC+ agrees to record production cuts amid COVID demand collapse",
                macro_regime="crisis",
                sanctions_intensity=0.0,
                oil_supply_impact=0.18,
                freight_impact=0.05,
                financial_enforcement_intensity=0.12,
                return_5d=0.045,
                return_20d=0.062,
                return_60d=0.145,
                commodity_return=0.052,
                producer_equity_return=0.058,
                broad_market_return=0.088,
                volatility_response=0.68,
                best_implementation="long_producers_with_hedges",
                worst_implementation="unhedged_direct_crude",
                max_drawdown=-0.152,
                time_to_peak_response_days=8,
                thesis_outcome="partially_confirmed",
                notes="High volatility hurt unhedged positions despite positive supply impact. Hedges were essential.",
            ),
            
            # 2019 Strait of Hormuz Tensions
            HistoricalEvent(
                event_id="hist_hormuz_2019_06",
                event_date=date(2019, 6, 13),
                fingerprint=SetupFingerprint(
                    event_type="shipping_risk",
                    region="middle_east",
                    asset_class="energy",
                    commodity="oil",
                    policy_mechanism="shipping_constraints",
                    supply_impact="high",
                    shipping_impact="very_high",
                    financial_enforcement="low",
                    market_regime="risk_off",
                    volatility_regime="elevated",
                ),
                description="Tanker attacks near Strait of Hormuz; shipping risk escalates",
                macro_regime="risk_off",
                sanctions_intensity=0.12,
                oil_supply_impact=0.16,
                freight_impact=0.45,
                financial_enforcement_intensity=0.08,
                return_5d=0.019,
                return_20d=0.071,
                return_60d=0.098,
                commodity_return=0.018,
                producer_equity_return=0.073,
                broad_market_return=-0.031,
                volatility_response=0.28,
                best_implementation="long_shipping_plus_energy",
                worst_implementation="isolated_xle",
                max_drawdown=-0.038,
                time_to_peak_response_days=16,
                thesis_outcome="confirmed",
                notes="Shipping risk premium drove outcomes. Including shipping plays enhanced returns.",
            ),
        ]
        
        for event in events:
            self.engine.register_historical_event(event)
        
        return events
    
    def load_historical_trades(self) -> List[HistoricalTrade]:
        """Load historical trade implementations and outcomes."""
        from learning.schemas import HistoricalTrade
        
        trades = [
            # Producer Equity + Index Hedge
            HistoricalTrade(
                trade_id="trade_001",
                event_id="hist_iran_2022_06",
                implementation_type="long_producers_plus_index_hedge",
                entry_date=date(2022, 6, 15),
                exit_date=date(2022, 7, 28),
                duration_days=43,
                initial_sizing=0.035,
                instruments=["XLE", "SPY_PUT_SPREADS"],
                return_realized=0.087,
                max_drawdown=-0.032,
                hedge_effectiveness=0.78,
                time_to_profit_days=6,
                outcome="success",
                notes="Hedge worked well; protected against market correction while capturing energy outperformance",
            ),
            
            # Direct Commodity (Underperforming)
            HistoricalTrade(
                trade_id="trade_002",
                event_id="hist_iran_2022_06",
                implementation_type="direct_crude_futures",
                entry_date=date(2022, 6, 15),
                exit_date=date(2022, 7, 28),
                duration_days=43,
                initial_sizing=0.03,
                instruments=["CL_FUTURES"],
                return_realized=0.024,
                max_drawdown=-0.055,
                hedge_effectiveness=0.0,
                time_to_profit_days=14,
                outcome="partial",
                notes="Direct crude underperformed due to rerouting. Unhedged drawdown hit hard before recovery.",
            ),
            
            # Diversified Energy
            HistoricalTrade(
                trade_id="trade_003",
                event_id="hist_ukraine_2021_11",
                implementation_type="diversified_energy_with_call_spreads",
                entry_date=date(2021, 11, 1),
                exit_date=date(2021, 12, 20),
                duration_days=49,
                initial_sizing=0.04,
                instruments=["XLE", "XOP", "FENY", "OIH_CALL_SPREADS"],
                return_realized=0.12,
                max_drawdown=-0.042,
                hedge_effectiveness=0.72,
                time_to_profit_days=8,
                outcome="success",
                notes="Diversification critical. Call spreads capped upside slightly but protected downside effectively.",
            ),
            
            # OPEC+ Hedged Position
            HistoricalTrade(
                trade_id="trade_004",
                event_id="hist_opec_2020_04",
                implementation_type="long_producers_with_hedges",
                entry_date=date(2020, 4, 12),
                exit_date=date(2020, 5, 29),
                duration_days=47,
                initial_sizing=0.032,
                instruments=["XLE", "DVN", "VLO", "PUT_SPREADS"],
                return_realized=0.058,
                max_drawdown=-0.089,
                hedge_effectiveness=0.65,
                time_to_profit_days=5,
                outcome="success",
                notes="Extreme volatility made hedges expensive but critical. Unhedged positions took 15% draws.",
            ),
            
            # Unhedged Direct (High Volatility Hit)
            HistoricalTrade(
                trade_id="trade_005",
                event_id="hist_opec_2020_04",
                implementation_type="unhedged_direct_crude",
                entry_date=date(2020, 4, 12),
                exit_date=date(2020, 5, 29),
                duration_days=47,
                initial_sizing=0.035,
                instruments=["CL_FUTURES"],
                return_realized=0.032,
                max_drawdown=-0.185,
                hedge_effectiveness=0.0,
                time_to_profit_days=18,
                outcome="partial",
                notes="Despite positive outcome, extreme volatility made journey painful. Drawdown exceeds position size.",
            ),
            
            # Shipping + Energy Play
            HistoricalTrade(
                trade_id="trade_006",
                event_id="hist_hormuz_2019_06",
                implementation_type="long_shipping_plus_energy",
                entry_date=date(2019, 6, 13),
                exit_date=date(2019, 8, 2),
                duration_days=50,
                initial_sizing=0.04,
                instruments=["XLE", "XSS", "IIF_SHIPPING_ETF"],
                return_realized=0.098,
                max_drawdown=-0.028,
                hedge_effectiveness=0.82,
                time_to_profit_days=7,
                outcome="success",
                notes="Shipping premium was significant. Multi-sector approach captured both supply and logistics upside.",
            ),
        ]
        
        for trade in trades:
            self.engine.register_historical_trade(trade)
        
        return trades
    
    def load_all(self) -> None:
        """Load all historical data into analog engine."""
        self.load_oil_geopolitical_events()
        self.load_historical_trades()


def create_historical_loader(analog_engine: AnalogEngine) -> HistoricalDataLoader:
    """Factory function to create and populate loader."""
    loader = HistoricalDataLoader(analog_engine)
    loader.load_all()
    return loader
