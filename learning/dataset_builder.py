"""
Training dataset builder.

Path: learning/dataset_builder.py

Combines feature store observations with outcome labels to create
supervised training datasets for model training.

Handles temporal alignment (matching observations to labels) and
walk-forward split generation for time-series validation.
"""

from datetime import date, datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from learning.schemas import (
    FeatureVector,
    TrainingLabel,
    WalkForwardSplit,
)
from learning.data_quality import FeatureStore


@dataclass
class TrainingExample:
    """Single training example: features + label."""
    observation_id: str
    features: Dict[str, float]
    label: float
    label_type: str
    timestamp: datetime
    horizon_days: int


class DatasetBuilder:
    """
    Builds supervised training datasets from feature store + labels.
    
    Manages temporal alignment and creates walk-forward splits for
    financial time-series modeling.
    """
    
    def __init__(self, feature_store: FeatureStore):
        self.feature_store = feature_store
        self.labels: Dict[str, List[TrainingLabel]] = {}
    
    def add_labels(self, labels: List[TrainingLabel]) -> None:
        """Register labels from outcome assessment."""
        for label in labels:
            if label.observation_id not in self.labels:
                self.labels[label.observation_id] = []
            self.labels[label.observation_id].append(label)
    
    def build_training_dataset(
        self,
        label_type: str,
        start_date: date,
        end_date: date,
    ) -> List[TrainingExample]:
        """
        Build training dataset for a specific label type.
        
        Matches observations from feature store to labels within date range.
        """
        examples: List[TrainingExample] = []
        
        # Get all labeled observation IDs
        for obs_id, label_list in self.labels.items():
            # Find labels of this type in date range
            matching_labels = [
                lbl for lbl in label_list
                if (lbl.label_type == label_type and
                    start_date <= lbl.measured_at.date() <= end_date and
                    lbl.is_valid)
            ]
            
            if not matching_labels:
                continue
            
            # Get features for this observation
            obs = self.feature_store.get_observation(obs_id)
            if not obs:
                continue
            
            # Create example for each label
            for label in matching_labels:
                example = TrainingExample(
                    observation_id=obs_id,
                    features=obs.features.copy(),
                    label=label.value,
                    label_type=label.label_type,
                    timestamp=obs.timestamp,
                    horizon_days=label.horizon_days,
                )
                examples.append(example)
        
        # Sort by timestamp for time-series ordering
        examples.sort(key=lambda e: e.timestamp)
        
        return examples
    
    def create_walk_forward_splits(
        self,
        all_data_start: date,
        all_data_end: date,
        training_window_years: int = 5,
        test_window_days: int = 60,
        step_days: int = 30,
    ) -> List[WalkForwardSplit]:
        """
        Create walk-forward validation splits for time-series data.
        
        Prevents lookahead bias by ensuring test set always follows training set.
        
        Example:
            training_window_years=5, test_window_days=60, step_days=30
            
            Split 1: Train 2018-2022, Test 2023-01 to 2023-03
            Split 2: Train 2018-2023-01, Test 2023-02 to 2023-04
            Split 3: Train 2018-2023-02, Test 2023-03 to 2023-05
            ...
        """
        splits: List[WalkForwardSplit] = []
        split_id = 0
        
        # Initial training window
        from datetime import timedelta
        
        training_days = training_window_years * 365
        
        current_test_start = all_data_start + timedelta(days=training_days)
        
        while current_test_start + timedelta(days=test_window_days) <= all_data_end:
            test_end = current_test_start + timedelta(days=test_window_days)
            
            # Get observations for training and test periods
            train_obs = self.feature_store.get_observations_by_date_range(
                datetime.combine(all_data_start, datetime.min.time()),
                datetime.combine(current_test_start, datetime.min.time()),
            )
            test_obs = self.feature_store.get_observations_by_date_range(
                datetime.combine(current_test_start, datetime.min.time()),
                datetime.combine(test_end, datetime.min.time()),
            )
            
            split = WalkForwardSplit(
                split_id=split_id,
                train_start=all_data_start,
                train_end=current_test_start,
                test_start=current_test_start,
                test_end=test_end,
                training_samples=len(train_obs),
                test_samples=len(test_obs),
            )
            splits.append(split)
            
            # Slide forward
            current_test_start = current_test_start + timedelta(days=step_days)
            split_id += 1
        
        return splits
    
    def split_by_walk_forward(
        self,
        examples: List[TrainingExample],
        split: WalkForwardSplit,
    ) -> Tuple[List[TrainingExample], List[TrainingExample]]:
        """
        Partition training examples into train/test per walk-forward split.
        """
        from datetime import datetime, timezone
        
        train_cutoff = datetime.combine(split.train_end, datetime.min.time()).replace(tzinfo=timezone.utc)
        test_cutoff = datetime.combine(split.test_end, datetime.min.time()).replace(tzinfo=timezone.utc)
        
        train_examples = [e for e in examples if e.timestamp <= train_cutoff]
        test_examples = [
            e for e in examples
            if train_cutoff < e.timestamp <= test_cutoff
        ]
        
        return train_examples, test_examples
    
    def get_feature_names(self) -> List[str]:
        """Get list of all feature names in store."""
        names = set()
        for obs in self.feature_store.observations.values():
            names.update(obs.features.keys())
        return sorted(list(names))
