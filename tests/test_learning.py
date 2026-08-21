"""
Unit tests for Learning Engine components.

Path: tests/test_learning.py

Tests the core learning pipeline:
- Data quality gates
- Outcome labeling
- Dataset building
- Model training
- Evaluation gates
- Model registry
- Analog retrieval
"""

import unittest
from datetime import datetime, date, timezone, timedelta
from pathlib import Path
import tempfile
import shutil

from learning.data_quality import DataQualityGateKeeper, DataQualityConfig, FeatureStore
from learning.schemas import FeatureVector, TrainingLabel, SetupFingerprint, HistoricalEvent
from learning.labels import OutcomeLabelingService
from learning.dataset_builder import DatasetBuilder, TrainingExample
from learning.models import ReturnModel, DrawdownModel
from learning.training import ModelTrainer
from learning.evaluation import ModelEvaluator
from learning.analogs import AnalogEngine, SetupEncoder, SimilarityCalculator
from learning.orchestrator import LearningOrchestrator


class TestDataQualityGates(unittest.TestCase):
    """Test data quality gate pipeline."""
    
    def setUp(self):
        config = DataQualityConfig(
            trusted_sources={"TEST_SOURCE"},
            outlier_std_threshold=3.0,
        )
        self.gatekeeper = DataQualityGateKeeper(config)
    
    def test_valid_observation_passes(self):
        """Valid observation should pass all gates."""
        obs = FeatureVector(
            observation_id="test_001",
            timestamp=datetime.now(timezone.utc),
            features={"feature_a": 1.5, "feature_b": 2.0},
        )
        
        gate = self.gatekeeper.validate_feature_vector(
            obs,
            datetime.now(timezone.utc),
            source="TEST_SOURCE",
        )
        
        self.assertTrue(gate.passed)
        self.assertEqual(gate.schema_valid, True)
        self.assertEqual(gate.timestamp_valid, True)
        self.assertEqual(gate.source_trusted, True)
    
    def test_untrusted_source_fails(self):
        """Observation from untrusted source should fail."""
        obs = FeatureVector(
            observation_id="test_002",
            timestamp=datetime.now(timezone.utc),
            features={"feature_a": 1.5},
        )
        
        gate = self.gatekeeper.validate_feature_vector(
            obs,
            datetime.now(timezone.utc),
            source="UNTRUSTED",
        )
        
        self.assertFalse(gate.passed)
        self.assertFalse(gate.source_trusted)
    
    def test_feature_store_stores_valid_observations(self):
        """Feature store should accept valid observations."""
        store = FeatureStore()
        
        obs = FeatureVector(
            observation_id="test_003",
            timestamp=datetime.now(timezone.utc),
            features={"feature_a": 1.0},
        )
        
        gate = self.gatekeeper.validate_feature_vector(
            obs,
            datetime.now(timezone.utc),
            source="TEST_SOURCE",
        )
        
        added = store.add_observation(obs, gate)
        self.assertTrue(added)
        self.assertEqual(store.size(), 1)


class TestOutcomeLabeling(unittest.TestCase):
    """Test outcome labeling service."""
    
    def setUp(self):
        self.labeler = OutcomeLabelingService()
    
    def test_label_profitable_trade(self):
        """Profitable trade should generate positive labels."""
        assessment, labels = self.labeler.label_trade_outcome(
            thesis_id="thesis_001",
            entry_date=date(2026, 1, 15),
            exit_date=date(2026, 2, 15),
            entry_price=100.0,
            exit_price=110.0,
            max_price_during_trade=115.0,
            min_price_during_trade=98.0,
            expected_return_target=0.08,
            expected_hedge_cost=0.02,
            realized_hedge_cost=0.019,
            expected_thesis_description="Positive outcome expected",
            actual_outcome_description="Thesis confirmed",
        )
        
        self.assertGreater(assessment.actual_return, 0)
        self.assertEqual(len(labels), 4)  # return, drawdown, thesis_success, hedge_effectiveness
        
        # Check return label
        return_label = next(l for l in labels if l.label_type == "return")
        self.assertGreater(return_label.value, 0)
    
    def test_label_assessment_breakdown(self):
        """Outcome assessment should provide multi-dimensional analysis."""
        assessment, _ = self.labeler.label_trade_outcome(
            thesis_id="thesis_002",
            entry_date=date(2026, 1, 15),
            exit_date=date(2026, 2, 15),
            entry_price=100.0,
            exit_price=108.0,
            max_price_during_trade=110.0,
            min_price_during_trade=99.0,
            expected_return_target=0.08,
            expected_hedge_cost=0.02,
            realized_hedge_cost=0.018,
            expected_thesis_description="Energy equities outperform",
            actual_outcome_description="Thesis confirmed; equities outperformed",
        )
        
        # Check that all dimensions are assigned
        self.assertIsNotNone(assessment.thesis_correctness)
        self.assertIsNotNone(assessment.instrument_correctness)
        self.assertIsNotNone(assessment.timing_correctness)
        self.assertIsNotNone(assessment.hedge_effectiveness)
        self.assertIsNotNone(assessment.sizing_appropriateness)


class TestDatasetBuilder(unittest.TestCase):
    """Test training dataset construction."""
    
    def setUp(self):
        self.store = FeatureStore()
        self.builder = DatasetBuilder(self.store)
    
    def test_build_dataset_from_features_and_labels(self):
        """Dataset builder should align features with labels."""
        # Add feature
        obs = FeatureVector(
            observation_id="obs_001",
            timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            features={"conviction": 0.8, "risk": 0.3},
        )
        config = DataQualityConfig(trusted_sources={"TEST"})
        gatekeeper = DataQualityGateKeeper(config)
        gate = gatekeeper.validate_feature_vector(obs, datetime.now(timezone.utc), "TEST")
        self.store.add_observation(obs, gate)
        
        # Add label
        label = TrainingLabel(
            observation_id="obs_001",
            label_type="return",
            value=0.12,
            measured_at=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            horizon_days=31,
            is_valid=True,
        )
        self.builder.add_labels([label])
        
        # Build dataset
        examples = self.builder.build_training_dataset(
            label_type="return",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 28),
        )
        
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0].observation_id, "obs_001")
        self.assertEqual(examples[0].label, 0.12)


class TestModelTraining(unittest.TestCase):
    """Test model training pipeline."""
    
    def setUp(self):
        self.store = FeatureStore()
        self.builder = DatasetBuilder(self.store)
    
    def test_simple_model_training(self):
        """Model training should work on minimal dataset."""
        # Create training examples
        examples = [
            TrainingExample(
                observation_id=f"obs_{i}",
                features={"feature_a": float(i), "feature_b": float(i*2)},
                label=float(i) * 0.1,
                label_type="return",
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=i),
                horizon_days=30,
            )
            for i in range(1, 11)
        ]
        
        model = ReturnModel()
        model.fit(examples)
        
        self.assertTrue(model.trained)
        self.assertGreater(len(model.feature_names), 0)
        
        # Test prediction
        pred = model.predict({"feature_a": 5.0, "feature_b": 10.0})
        self.assertIsInstance(pred, float)


class TestModelEvaluation(unittest.TestCase):
    """Test model evaluation gates."""
    
    def test_evaluation_gates(self):
        """Model evaluator should assess multiple gates."""
        from learning.schemas import ModelCard, ModelMetrics
        
        metrics = ModelMetrics(
            out_of_sample_sharpe=0.8,
            max_drawdown=-0.10,
            calibration_error=0.08,
            r_squared=0.45,
        )
        
        card = ModelCard(
            model_id="test_model_001",
            model_type="return",
            version="1.0",
            trained_at=datetime.now(timezone.utc),
            training_start_date=date(2018, 1, 1),
            training_end_date=date(2026, 1, 1),
            feature_names=["f1", "f2", "f3"],
            feature_count=3,
            training_sample_size=1000,
            out_of_sample_sample_size=100,
            metrics=metrics,
            model_code_version="1.0",
            model_parameters={},
            status="draft",
        )
        
        evaluator = ModelEvaluator()
        gates, all_passed = evaluator.evaluate_candidate(card)
        
        self.assertGreater(len(gates), 0)
        # Should pass OOS performance gate with Sharpe 0.8
        oos_gate = next(g for g in gates if g.gate_name == "oos_performance")
        self.assertTrue(oos_gate.passed)


class TestAnalogRetrieval(unittest.TestCase):
    """Test analog retrieval engine."""
    
    def test_setup_encoding(self):
        """Setup fingerprints should encode correctly."""
        encoder = SetupEncoder()
        
        fingerprint = encoder.encode_setup(
            event_type="secondary_sanctions",
            region="middle_east",
            commodity="oil",
            supply_impact="high",
        )
        
        self.assertEqual(fingerprint.event_type, "secondary_sanctions")
        self.assertEqual(fingerprint.region, "middle_east")
        self.assertEqual(fingerprint.commodity, "oil")
    
    def test_similarity_calculation(self):
        """Similarity calculator should score fingerprint similarity."""
        calculator = SimilarityCalculator()
        
        fp1 = SetupFingerprint(
            event_type="sanctions",
            region="middle_east",
            commodity="oil",
            supply_impact="high",
        )
        
        fp2 = SetupFingerprint(
            event_type="sanctions",
            region="middle_east",
            commodity="oil",
            supply_impact="high",
        )
        
        similarity, components = calculator.similarity(fp1, fp2)
        
        self.assertEqual(similarity, 1.0)  # Identical fingerprints
        self.assertIn("event_type", components)
        self.assertEqual(components["event_type"], 1.0)
    
    def test_analog_engine_integration(self):
        """Analog engine should retrieve and rank similar events."""
        engine = AnalogEngine()
        
        # Register a historical event
        event = HistoricalEvent(
            event_id="hist_001",
            event_date=date(2023, 6, 15),
            fingerprint=SetupFingerprint(
                event_type="sanctions",
                region="middle_east",
                commodity="oil",
                supply_impact="high",
            ),
            description="Iran sanctions escalation",
            macro_regime="risk_off",
            sanctions_intensity=0.85,
            oil_supply_impact=0.12,
            return_5d=0.02,
            return_20d=0.08,
            return_60d=0.15,
        )
        engine.register_historical_event(event)
        
        # Find analogs for similar setup
        current_setup = SetupFingerprint(
            event_type="sanctions",
            region="middle_east",
            commodity="oil",
            supply_impact="high",
        )
        
        analog_set = engine.find_analogs(current_setup, implementation_type="long_producers")
        
        self.assertGreater(len(analog_set.event_analogs), 0)


class TestLearningOrchestrator(unittest.TestCase):
    """Test end-to-end learning orchestration."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orchestrator = LearningOrchestrator(workspace_dir=self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_end_to_end_workflow(self):
        """End-to-end learning workflow should work."""
        # 1. Ingest observation
        obs = FeatureVector(
            observation_id="test_001",
            timestamp=datetime.now(timezone.utc),
            features={"conviction": 0.8, "risk": 0.2},
        )
        
        success, gate = self.orchestrator.ingest_observation(obs, "EDGE_RESEARCH")
        self.assertTrue(success)
        
        # 2. Label outcome (simulated)
        assessment, labels = self.orchestrator.label_trade_outcome(
            thesis_id="thesis_001",
            entry_date=date(2026, 1, 15),
            exit_date=date(2026, 2, 15),
            entry_price=100.0,
            exit_price=110.0,
            max_price=112.0,
            min_price=99.0,
            expected_return=0.08,
            expected_hedge_cost=0.02,
            realized_hedge_cost=0.019,
            expected_thesis="Positive",
            actual_outcome="Confirmed",
        )
        
        self.assertEqual(len(labels), 4)
        
        # 3. Retrieve analogs
        analogs = self.orchestrator.find_analogs(
            event_type="sanctions",
            region="middle_east",
            min_similarity=0.50,
        )
        
        self.assertIsNotNone(analogs["confidence"])


if __name__ == "__main__":
    unittest.main()
