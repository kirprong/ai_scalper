"""
A/B Testing Framework - TASK-027

Provides experiment management, traffic splitting, metrics collection,
and statistical significance testing for model comparison.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import json
import logging
import hashlib
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class Variant:
    """Represents a single variant in an A/B test"""
    variant_id: str
    version_id: str  # Model version ID
    traffic_ratio: float  # Percentage of traffic (0.0 to 1.0)
    metrics: Dict[str, List[float]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "version_id": self.version_id,
            "traffic_ratio": self.traffic_ratio,
            "metrics": self.metrics,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Variant":
        return cls(
            variant_id=data["variant_id"],
            version_id=data["version_id"],
            traffic_ratio=data["traffic_ratio"],
            metrics=data.get("metrics", {}),
        )


@dataclass
class Experiment:
    """Represents an A/B testing experiment"""
    experiment_id: str
    name: str
    model_type: str  # "lstm" or "xgboost"
    variants: List[Variant]
    status: str = "created"  # created, running, paused, completed
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    winner: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "model_type": self.model_type,
            "variants": [v.to_dict() for v in self.variants],
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "winner": self.winner,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Experiment":
        return cls(
            experiment_id=data["experiment_id"],
            name=data["name"],
            model_type=data["model_type"],
            variants=[Variant.from_dict(v) for v in data["variants"]],
            status=data["status"],
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            winner=data.get("winner"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class StatisticalResult:
    """Result of statistical significance test"""
    test_name: str
    statistic: float
    p_value: float
    is_significant: bool
    confidence_level: float
    effect_size: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "is_significant": self.is_significant,
            "confidence_level": self.confidence_level,
            "effect_size": self.effect_size,
        }


class ABTestingFramework:
    """
    A/B Testing Framework for model comparison.
    
    Features:
    - Experiment registration with variants
    - Hash-based traffic splitting (consistent user assignment)
    - Metrics collection per variant
    - Statistical significance testing (t-test, chi-square)
    - Automatic winner selection
    """
    
    def __init__(self, storage_path: str = "checkpoints/experiments.json"):
        self.storage_path = Path(storage_path)
        self.experiments: Dict[str, Experiment] = {}
        self._load_experiments()
    
    def _load_experiments(self):
        """Load experiments from storage"""
        if not self.storage_path.exists():
            logger.info("No existing experiments found, starting fresh")
            return
        
        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)
            
            self.experiments = {
                exp_id: Experiment.from_dict(exp_data)
                for exp_id, exp_data in data.get("experiments", {}).items()
            }
            
            logger.info(f"Loaded {len(self.experiments)} experiments")
        except Exception as e:
            logger.error(f"Failed to load experiments: {e}")
            self.experiments = {}
    
    def _save_experiments(self):
        """Save experiments to storage"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "experiments": {
                exp_id: exp.to_dict()
                for exp_id, exp in self.experiments.items()
            }
        }
        
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved {len(self.experiments)} experiments")
    
    def register_experiment(
        self,
        name: str,
        model_type: str,
        variants: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Experiment:
        """
        Register a new A/B testing experiment.
        
        Args:
            name: Experiment name
            model_type: Model type ("lstm" or "xgboost")
            variants: List of variant configs with variant_id, version_id, traffic_ratio
            metadata: Optional metadata
            
        Returns:
            Created Experiment
        """
        # Validate model type
        if model_type not in ["lstm", "xgboost"]:
            raise ValueError(f"Invalid model type: {model_type}")
        
        # Validate traffic ratios sum to 1.0
        total_traffic = sum(v.get("traffic_ratio", 0) for v in variants)
        if abs(total_traffic - 1.0) > 0.01:
            raise ValueError(f"Traffic ratios must sum to 1.0, got {total_traffic}")
        
        # Generate experiment ID
        experiment_id = f"{model_type}-{name.lower().replace(' ', '-')}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create variants
        variant_objects = [
            Variant(
                variant_id=v["variant_id"],
                version_id=v["version_id"],
                traffic_ratio=v["traffic_ratio"],
                metrics={"predictions": [], "actuals": [], "accuracy": []},
            )
            for v in variants
        ]
        
        # Create experiment
        experiment = Experiment(
            experiment_id=experiment_id,
            name=name,
            model_type=model_type,
            variants=variant_objects,
            status="created",
            metadata=metadata or {},
        )
        
        self.experiments[experiment_id] = experiment
        self._save_experiments()
        
        logger.info(f"Registered experiment: {experiment_id}")
        return experiment
    
    def start_experiment(self, experiment_id: str) -> bool:
        """Start an experiment"""
        if experiment_id not in self.experiments:
            logger.warning(f"Experiment not found: {experiment_id}")
            return False
        
        experiment = self.experiments[experiment_id]
        
        if experiment.status != "created":
            logger.warning(f"Experiment already started: {experiment.status}")
            return False
        
        experiment.status = "running"
        experiment.started_at = datetime.now()
        self._save_experiments()
        
        logger.info(f"Started experiment: {experiment_id}")
        return True
    
    def pause_experiment(self, experiment_id: str) -> bool:
        """Pause a running experiment"""
        if experiment_id not in self.experiments:
            return False
        
        experiment = self.experiments[experiment_id]
        
        if experiment.status != "running":
            return False
        
        experiment.status = "paused"
        self._save_experiments()
        
        logger.info(f"Paused experiment: {experiment_id}")
        return True
    
    def complete_experiment(self, experiment_id: str, winner: Optional[str] = None) -> bool:
        """Complete an experiment"""
        if experiment_id not in self.experiments:
            return False
        
        experiment = self.experiments[experiment_id]
        experiment.status = "completed"
        experiment.completed_at = datetime.now()
        experiment.winner = winner
        self._save_experiments()
        
        logger.info(f"Completed experiment: {experiment_id}, winner: {winner}")
        return True
    
    def assign_variant(self, experiment_id: str, user_id: str) -> Optional[Variant]:
        """
        Assign a variant to a user using hash-based consistent assignment.
        
        Args:
            experiment_id: Experiment ID
            user_id: User identifier
            
        Returns:
            Assigned Variant or None
        """
        if experiment_id not in self.experiments:
            return None
        
        experiment = self.experiments[experiment_id]
        
        if experiment.status != "running":
            return None
        
        # Hash-based assignment for consistency
        hash_input = f"{experiment_id}:{user_id}".encode()
        hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
        hash_ratio = (hash_value % 10000) / 10000.0
        
        # Assign variant based on traffic ratios
        cumulative = 0.0
        for variant in experiment.variants:
            cumulative += variant.traffic_ratio
            if hash_ratio <= cumulative:
                logger.debug(f"Assigned variant {variant.variant_id} to user {user_id}")
                return variant
        
        # Fallback to last variant
        return experiment.variants[-1]
    
    def record_metrics(
        self,
        experiment_id: str,
        variant_id: str,
        prediction: float,
        actual: float,
        accuracy: float,
    ):
        """Record metrics for a variant"""
        if experiment_id not in self.experiments:
            return
        
        experiment = self.experiments[experiment_id]
        
        for variant in experiment.variants:
            if variant.variant_id == variant_id:
                variant.metrics["predictions"].append(prediction)
                variant.metrics["actuals"].append(actual)
                variant.metrics["accuracy"].append(accuracy)
                self._save_experiments()
                return
        
        logger.warning(f"Variant not found: {variant_id}")
    
    def calculate_statistical_significance(
        self,
        experiment_id: str,
        metric: str = "accuracy",
        confidence_level: float = 0.95,
    ) -> Optional[StatisticalResult]:
        """
        Calculate statistical significance between variants.
        
        Args:
            experiment_id: Experiment ID
            metric: Metric to compare
            confidence_level: Confidence level (default: 0.95)
            
        Returns:
            StatisticalResult or None
        """
        if experiment_id not in self.experiments:
            return None
        
        experiment = self.experiments[experiment_id]
        
        if len(experiment.variants) < 2:
            return None
        
        # Get metrics for first two variants
        variant_a = experiment.variants[0]
        variant_b = experiment.variants[1]
        
        metrics_a = variant_a.metrics.get(metric, [])
        metrics_b = variant_b.metrics.get(metric, [])
        
        if len(metrics_a) < 10 or len(metrics_b) < 10:
            logger.warning("Insufficient data for statistical test")
            return None
        
        # Perform t-test
        t_stat, p_value = stats.ttest_ind(metrics_a, metrics_b)
        
        # Calculate effect size (Cohen's d)
        mean_a = np.mean(metrics_a)
        mean_b = np.mean(metrics_b)
        std_a = np.std(metrics_a)
        std_b = np.std(metrics_b)
        pooled_std = np.sqrt((std_a**2 + std_b**2) / 2)
        effect_size = (mean_b - mean_a) / pooled_std if pooled_std > 0 else 0.0
        
        # Determine significance
        alpha = 1 - confidence_level
        is_significant = p_value < alpha
        
        return StatisticalResult(
            test_name="t-test",
            statistic=t_stat,
            p_value=p_value,
            is_significant=is_significant,
            confidence_level=confidence_level,
            effect_size=effect_size,
        )
    
    def select_winner(self, experiment_id: str) -> Optional[str]:
        """
        Automatically select winner based on statistical significance.
        
        Returns:
            Winning variant_id or None
        """
        if experiment_id not in self.experiments:
            return None
        
        experiment = self.experiments[experiment_id]
        
        # Calculate significance
        result = self.calculate_statistical_significance(experiment_id)
        
        if result is None or not result.is_significant:
            return None
        
        # Compare means
        variant_a = experiment.variants[0]
        variant_b = experiment.variants[1]
        
        mean_a = np.mean(variant_a.metrics.get("accuracy", [0]))
        mean_b = np.mean(variant_b.metrics.get("accuracy", [0]))
        
        winner = variant_b.variant_id if mean_b > mean_a else variant_a.variant_id
        
        logger.info(f"Selected winner: {winner} for experiment {experiment_id}")
        return winner
    
    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get experiment by ID"""
        return self.experiments.get(experiment_id)
    
    def list_experiments(self, status: Optional[str] = None) -> List[Experiment]:
        """List experiments, optionally filtered by status"""
        experiments = list(self.experiments.values())
        
        if status:
            experiments = [e for e in experiments if e.status == status]
        
        return experiments
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get framework statistics"""
        return {
            "total_experiments": len(self.experiments),
            "by_status": {
                status: len([e for e in self.experiments.values() if e.status == status])
                for status in ["created", "running", "paused", "completed"]
            },
        }
