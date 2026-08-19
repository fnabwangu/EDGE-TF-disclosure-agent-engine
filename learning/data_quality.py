"""
Data quality gates for learning pipeline.

Path: learning/data_quality.py

All incoming data must pass deterministic validation gates before entering
the feature store or training datasets. Gates check schema, provenance,
timestamps, duplicates, outliers, missing values, and lookahead bias.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

from learning.schemas import DataQualityGate, FeatureVector


@dataclass
class DataQualityConfig:
    """Configuration for quality gates."""
    trusted_sources: Set[str]
    max_lookahead_days: int = 0
    outlier_std_threshold: float = 3.0
    missing_value_threshold: float = 0.2  # Allow up to 20% missing
    timestamp_tolerance_seconds: int = 300


class DataQualityGateKeeper:
    """Validates incoming data before feature store entry."""
    
    def __init__(self, config: DataQualityConfig):
        self.config = config
        self.seen_ids: Set[str] = set()
        self.feature_statistics: Dict[str, Dict[str, float]] = {}
    
    def validate_feature_vector(
        self,
        observation: FeatureVector,
        current_time: datetime,
        source: str,
    ) -> DataQualityGate:
        """
        Comprehensive validation of incoming feature vector.
        
        Returns DataQualityGate with passed=True only if all checks pass.
        """
        issues: List[str] = []
        
        # Check 1: Schema validity
        schema_valid = self._check_schema(observation)
        if not schema_valid:
            issues.append("schema_invalid")
        
        # Check 2: Timestamp validity
        timestamp_valid = self._check_timestamp(observation.timestamp, current_time)
        if not timestamp_valid:
            issues.append("timestamp_invalid")
        
        # Check 3: Source trust
        source_trusted = source in self.config.trusted_sources
        if not source_trusted:
            issues.append(f"source_not_trusted: {source}")
        
        # Check 4: Duplicate detection
        not_duplicate = observation.observation_id not in self.seen_ids
        if not not_duplicate:
            issues.append("duplicate_observation")
        
        # Check 5: Outlier detection
        not_outlier = self._check_outliers(observation)
        if not not_outlier:
            issues.append("outlier_detected")
        
        # Check 6: Missing values
        missing_values_acceptable = self._check_missing_values(observation)
        if not missing_values_acceptable:
            issues.append("excessive_missing_values")
        
        # Check 7: Lookahead bias (data should not be from future)
        no_lookahead = self._check_no_lookahead(observation.timestamp, current_time)
        if not no_lookahead:
            issues.append("potential_lookahead_bias")
        
        # Update seen IDs
        if not_duplicate:
            self.seen_ids.add(observation.observation_id)
        
        passed = all([
            schema_valid,
            timestamp_valid,
            source_trusted,
            not_duplicate,
            not_outlier,
            missing_values_acceptable,
            no_lookahead,
        ])
        
        return DataQualityGate(
            observation_id=observation.observation_id,
            schema_valid=schema_valid,
            timestamp_valid=timestamp_valid,
            source_trusted=source_trusted,
            not_duplicate=not_duplicate,
            not_outlier=not_outlier,
            missing_values_acceptable=missing_values_acceptable,
            no_lookahead_bias=no_lookahead,
            passed=passed,
            quality_issues=issues,
        )
    
    def _check_schema(self, observation: FeatureVector) -> bool:
        """Verify observation has required fields."""
        return (
            isinstance(observation.observation_id, str)
            and len(observation.observation_id) > 0
            and isinstance(observation.timestamp, datetime)
            and isinstance(observation.features, dict)
            and len(observation.features) > 0
            and all(isinstance(v, (int, float)) for v in observation.features.values())
        )
    
    def _check_timestamp(self, timestamp: datetime, current_time: datetime) -> bool:
        """Verify timestamp is reasonable."""
        # Allow timestamps within ±tolerance of current time
        delta = abs((current_time - timestamp).total_seconds())
        return delta <= self.config.timestamp_tolerance_seconds
    
    def _check_outliers(self, observation: FeatureVector) -> bool:
        """Detect outliers using z-score."""
        for feature_name, value in observation.features.items():
            if not isinstance(value, (int, float)):
                return False
            
            if feature_name not in self.feature_statistics:
                self.feature_statistics[feature_name] = {
                    "mean": 0.0,
                    "std": 1.0,
                    "count": 0,
                    "sum": 0.0,
                    "sum_sq": 0.0,
                }
            
            stats = self.feature_statistics[feature_name]
            stats["count"] += 1
            stats["sum"] += value
            stats["sum_sq"] += value ** 2
            stats["mean"] = stats["sum"] / stats["count"]
            
            if stats["count"] > 1:
                variance = (stats["sum_sq"] / stats["count"]) - (stats["mean"] ** 2)
                stats["std"] = max(1.0, variance ** 0.5)
                
                z_score = abs((value - stats["mean"]) / stats["std"])
                if z_score > self.config.outlier_std_threshold:
                    return False
        
        return True
    
    def _check_missing_values(self, observation: FeatureVector) -> bool:
        """Check that missing values don't exceed threshold."""
        if not observation.features:
            return False
        
        # If features dict is sparse, we consider missing values
        # This is a basic check; in practice you might track expected features
        total_possible = len(observation.features)
        missing_count = sum(
            1 for v in observation.features.values()
            if v is None or (isinstance(v, float) and v != v)  # NaN check
        )
        
        missing_ratio = missing_count / max(1, total_possible)
        return missing_ratio <= self.config.missing_value_threshold
    
    def _check_no_lookahead(self, timestamp: datetime, current_time: datetime) -> bool:
        """Prevent lookahead bias: data should not be from the future."""
        lookahead_seconds = (timestamp - current_time).total_seconds()
        return lookahead_seconds <= self.config.max_lookahead_days * 86400


class FeatureStore:
    """
    Append-only feature store for training data.
    
    Incoming observations pass quality gates and are indexed for efficient
    retrieval by time range or observation ID.
    """
    
    def __init__(self):
        self.observations: Dict[str, FeatureVector] = {}
        self.chronological_index: List[str] = []  # observation IDs in time order
        self.feature_index: Dict[str, List[str]] = {}  # feature_name -> [obs_ids]
    
    def add_observation(self, observation: FeatureVector, quality_gate: DataQualityGate) -> bool:
        """
        Add validated observation to feature store.
        
        Returns True if added, False if rejected.
        """
        if not quality_gate.passed:
            return False
        
        if observation.observation_id in self.observations:
            return False  # Duplicate
        
        self.observations[observation.observation_id] = observation
        self.chronological_index.append(observation.observation_id)
        self.chronological_index.sort(
            key=lambda oid: self.observations[oid].timestamp
        )
        
        # Update feature index
        for feature_name in observation.features.keys():
            if feature_name not in self.feature_index:
                self.feature_index[feature_name] = []
            self.feature_index[feature_name].append(observation.observation_id)
        
        return True
    
    def get_observations_by_date_range(
        self,
        start: datetime,
        end: datetime,
    ) -> List[FeatureVector]:
        """Retrieve all observations in date range (inclusive)."""
        result = []
        for oid in self.chronological_index:
            obs = self.observations[oid]
            if start <= obs.timestamp <= end:
                result.append(obs)
        return result
    
    def get_observation(self, observation_id: str) -> Optional[FeatureVector]:
        """Retrieve single observation by ID."""
        return self.observations.get(observation_id)
    
    def size(self) -> int:
        """Total observations in store."""
        return len(self.observations)
