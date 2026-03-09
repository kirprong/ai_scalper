"""
Experiment Manager - TASK-027

Manages experiment lifecycle with automatic winner selection,
early stopping rules, and integration with ModelVersioningSystem.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

from backend.evolution.ab_testing import ABTestingFramework, Experiment
from backend.evolution.model_versioning import ModelVersioningSystem

logger = logging.getLogger(__name__)


@dataclass
class EarlyStoppingConfig:
    """Configuration for early stopping rules"""
    min_samples: int = 100  # Minimum samples before early stopping
    significance_threshold: float = 0.01  # p-value threshold
    min_effect_size: float = 0.1  # Minimum Cohen's d
    check_interval_hours: int = 6  # Check every 6 hours


class ExperimentManager:
    """
    Manages experiment lifecycle with:
    - Start/stop/pause experiments
    - Automatic winner selection
    - Early stopping rules
    - Integration with ModelVersioningSystem
    """
    
    def __init__(
        self,
        ab_framework: ABTestingFramework,
        versioning_system: ModelVersioningSystem,
        early_stopping_config: Optional[EarlyStoppingConfig] = None,
    ):
        self.ab_framework = ab_framework
        self.versioning_system = versioning_system
        self.early_stopping_config = early_stopping_config or EarlyStoppingConfig()
        self.last_check_time: Optional[datetime] = None
    
    def create_experiment(
        self,
        name: str,
        model_type: str,
        control_version: str,
        treatment_version: str,
        traffic_split: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Experiment:
        """
        Create a new A/B experiment.
        
        Args:
            name: Experiment name
            model_type: Model type ("lstm" or "xgboost")
            control_version: Control version ID (baseline)
            treatment_version: Treatment version ID (new model)
            traffic_split: Traffic split ratio (default: 0.5 for 50/50)
            metadata: Optional metadata
            
        Returns:
            Created Experiment
        """
        # Verify versions exist
        control = self.versioning_system.get_version(control_version)
        treatment = self.versioning_system.get_version(treatment_version)
        
        if not control:
            raise ValueError(f"Control version not found: {control_version}")
        if not treatment:
            raise ValueError(f"Treatment version not found: {treatment_version}")
        
        # Create variants
        variants = [
            {
                "variant_id": "control",
                "version_id": control_version,
                "traffic_ratio": traffic_split,
            },
            {
                "variant_id": "treatment",
                "version_id": treatment_version,
                "traffic_ratio": 1.0 - traffic_split,
            },
        ]
        
        # Register experiment
        experiment = self.ab_framework.register_experiment(
            name=name,
            model_type=model_type,
            variants=variants,
            metadata=metadata,
        )
        
        logger.info(f"Created experiment: {experiment.experiment_id}")
        return experiment
    
    def start_experiment(self, experiment_id: str) -> bool:
        """Start an experiment"""
        return self.ab_framework.start_experiment(experiment_id)
    
    def pause_experiment(self, experiment_id: str) -> bool:
        """Pause an experiment"""
        return self.ab_framework.pause_experiment(experiment_id)
    
    def stop_experiment(self, experiment_id: str, winner: Optional[str] = None) -> bool:
        """
        Stop an experiment and optionally activate winner.
        
        Args:
            experiment_id: Experiment ID
            winner: Winning variant_id (auto-detected if None)
            
        Returns:
            Success status
        """
        experiment = self.ab_framework.get_experiment(experiment_id)
        if not experiment:
            return False
        
        # Auto-select winner if not provided
        if winner is None:
            winner = self.ab_framework.select_winner(experiment_id)
        
        # Complete experiment
        success = self.ab_framework.complete_experiment(experiment_id, winner)
        
        if success and winner:
            # Activate winning version
            winner_variant = None
            for variant in experiment.variants:
                if variant.variant_id == winner:
                    winner_variant = variant
                    break
            
            if winner_variant:
                self.versioning_system.activate_model(winner_variant.version_id)
                logger.info(f"Activated winning version: {winner_variant.version_id}")
        
        return success
    
    def check_early_stopping(self, experiment_id: str) -> Optional[str]:
        """
        Check if early stopping criteria are met.
        
        Returns:
            Winning variant_id if early stopping triggered, None otherwise
        """
        experiment = self.ab_framework.get_experiment(experiment_id)
        if not experiment or experiment.status != "running":
            return None
        
        # Check sample size
        total_samples = sum(
            len(v.metrics.get("accuracy", []))
            for v in experiment.variants
        )
        
        if total_samples < self.early_stopping_config.min_samples:
            return None
        
        # Calculate statistical significance
        result = self.ab_framework.calculate_statistical_significance(experiment_id)
        
        if result is None:
            return None
        
        # Check early stopping criteria
        if (result.p_value < self.early_stopping_config.significance_threshold and
            abs(result.effect_size) >= self.early_stopping_config.min_effect_size):
            
            winner = self.ab_framework.select_winner(experiment_id)
            logger.info(f"Early stopping triggered for {experiment_id}, winner: {winner}")
            return winner
        
        return None
    
    def run_periodic_check(self) -> Dict[str, str]:
        """
        Run periodic check on all running experiments.
        
        Returns:
            Dict of experiment_id -> winner for early stopped experiments
        """
        self.last_check_time = datetime.now()
        early_stopped = {}
        
        running_experiments = self.ab_framework.list_experiments(status="running")
        
        for experiment in running_experiments:
            winner = self.check_early_stopping(experiment.experiment_id)
            if winner:
                self.stop_experiment(experiment.experiment_id, winner)
                early_stopped[experiment.experiment_id] = winner
        
        return early_stopped
    
    def get_experiment_status(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed experiment status"""
        experiment = self.ab_framework.get_experiment(experiment_id)
        if not experiment:
            return None
        
        # Calculate metrics
        metrics = {}
        for variant in experiment.variants:
            accuracies = variant.metrics.get("accuracy", [])
            if accuracies:
                import numpy as np
                metrics[variant.variant_id] = {
                    "samples": len(accuracies),
                    "mean_accuracy": float(np.mean(accuracies)),
                    "std_accuracy": float(np.std(accuracies)),
                }
        
        # Get statistical significance
        significance = self.ab_framework.calculate_statistical_significance(experiment_id)
        
        return {
            "experiment_id": experiment.experiment_id,
            "name": experiment.name,
            "status": experiment.status,
            "model_type": experiment.model_type,
            "variants": metrics,
            "statistical_significance": significance.to_dict() if significance else None,
            "winner": experiment.winner,
            "started_at": experiment.started_at.isoformat() if experiment.started_at else None,
            "completed_at": experiment.completed_at.isoformat() if experiment.completed_at else None,
        }
    
    def list_active_experiments(self) -> List[Dict[str, Any]]:
        """List all active experiments with status"""
        experiments = self.ab_framework.list_experiments(status="running")
        return [
            self.get_experiment_status(exp.experiment_id)
            for exp in experiments
        ]
    
    def get_recommendations(self) -> List[Dict[str, Any]]:
        """Get recommendations for experiments"""
        recommendations = []
        
        # Check for experiments ready for early stopping
        running = self.ab_framework.list_experiments(status="running")
        for exp in running:
            winner = self.check_early_stopping(exp.experiment_id)
            if winner:
                recommendations.append({
                    "experiment_id": exp.experiment_id,
                    "type": "early_stopping",
                    "message": f"Experiment ready for early stopping. Winner: {winner}",
                    "winner": winner,
                })
        
        # Check for experiments with insufficient data
        for exp in running:
            total_samples = sum(
                len(v.metrics.get("accuracy", []))
                for v in exp.variants
            )
            if total_samples < self.early_stopping_config.min_samples:
                recommendations.append({
                    "experiment_id": exp.experiment_id,
                    "type": "insufficient_data",
                    "message": f"Experiment needs more data: {total_samples}/{self.early_stopping_config.min_samples} samples",
                })
        
        return recommendations
