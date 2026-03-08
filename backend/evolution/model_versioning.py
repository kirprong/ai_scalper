"""
Model Versioning System - TASK-026

Manages model versions with semantic versioning, metadata tracking,
activation/deactivation, rollback, and comparison capabilities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import json
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    """Represents a single model version"""
    
    version_id: str  # Semantic version (e.g., "v1.0.0")
    model_type: str  # "lstm" or "xgboost"
    created_at: datetime
    metrics: Dict[str, Any]  # accuracy, loss, training_samples, etc.
    file_path: str  # Path to model file
    is_active: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "version_id": self.version_id,
            "model_type": self.model_type,
            "created_at": self.created_at.isoformat(),
            "metrics": self.metrics,
            "file_path": self.file_path,
            "is_active": self.is_active,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelVersion":
        """Create from dictionary"""
        return cls(
            version_id=data["version_id"],
            model_type=data["model_type"],
            created_at=datetime.fromisoformat(data["created_at"]),
            metrics=data["metrics"],
            file_path=data["file_path"],
            is_active=data.get("is_active", False),
        )


@dataclass
class VersionComparison:
    """Result of comparing two model versions"""
    
    version_id_1: str
    version_id_2: str
    metrics_diff: Dict[str, float]  # Difference in metrics
    winner: Optional[str] = None  # Which version is better
    improvement_pct: Dict[str, float] = field(default_factory=dict)  # Percentage improvement
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "version_id_1": self.version_id_1,
            "version_id_2": self.version_id_2,
            "metrics_diff": self.metrics_diff,
            "winner": self.winner,
            "improvement_pct": self.improvement_pct,
        }


class ModelVersioningSystem:
    """
    System for managing model versions with semantic versioning.
    
    Features:
    - Register new model versions
    - Track version metadata (accuracy, loss, training_samples)
    - Activate/deactivate models
    - Rollback to previous versions
    - Compare model metrics between versions
    """
    
    def __init__(self, storage_path: str = "checkpoints/versions.json"):
        """
        Initialize versioning system.
        
        Args:
            storage_path: Path to JSON file for version storage
        """
        self.storage_path = Path(storage_path)
        self.versions: Dict[str, List[ModelVersion]] = {}  # model_type -> versions
        self.active_versions: Dict[str, str] = {}  # model_type -> version_id
        
        # Load existing versions
        self._load_versions()
    
    def _load_versions(self):
        """Load versions from storage file"""
        if not self.storage_path.exists():
            logger.info("No existing version storage found, starting fresh")
            return
        
        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)
            
            # Load versions by model type
            for model_type, version_list in data.get("versions", {}).items():
                self.versions[model_type] = [
                    ModelVersion.from_dict(v) for v in version_list
                ]
            
            # Load active versions
            self.active_versions = data.get("active_versions", {})
            
            logger.info(f"Loaded {sum(len(v) for v in self.versions.values())} versions from storage")
            
        except Exception as e:
            logger.error(f"Failed to load versions: {e}")
            self.versions = {}
            self.active_versions = {}
    
    def _save_versions(self):
        """Save versions to storage file"""
        # Ensure directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "versions": {
                model_type: [v.to_dict() for v in versions]
                for model_type, versions in self.versions.items()
            },
            "active_versions": self.active_versions,
        }
        
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved versions to {self.storage_path}")
    
    def _parse_version(self, version_id: str) -> tuple:
        """
        Parse semantic version string.
        
        Args:
            version_id: Version string (e.g., "lstm-v1.0.0" or "v1.0.0")
            
        Returns:
            Tuple of (major, minor, patch)
        """
        # Support both old format (v1.0.0) and new format (lstm-v1.0.0)
        match = re.search(r"v(\d+)\.(\d+)\.(\d+)", version_id)
        if not match:
            raise ValueError(f"Invalid version format: {version_id}. Expected format: v1.0.0 or model-v1.0.0")
        
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    
    def _get_next_version(self, model_type: str) -> str:
        """
        Get next semantic version for a model type.
        
        Args:
            model_type: Model type (lstm, xgboost)
            
        Returns:
            Next version string (e.g., "lstm-v1.0.1")
        """
        if model_type not in self.versions or not self.versions[model_type]:
            return f"{model_type}-v1.0.0"
        
        # Get latest version
        latest = self.versions[model_type][-1]
        major, minor, patch = self._parse_version(latest.version_id)
        
        # Increment patch version
        return f"{model_type}-v{major}.{minor}.{patch + 1}"
    
    def register_model(
        self,
        model_type: str,
        file_path: str,
        metrics: Dict[str, Any],
        version_id: Optional[str] = None,
    ) -> ModelVersion:
        """
        Register a new model version.
        
        Args:
            model_type: Model type (lstm, xgboost)
            file_path: Path to model file
            metrics: Model metrics (accuracy, loss, training_samples, etc.)
            version_id: Optional version ID (auto-generated if None)
            
        Returns:
            Created ModelVersion
        """
        # Validate model type
        if model_type not in ["lstm", "xgboost"]:
            raise ValueError(f"Invalid model type: {model_type}. Must be 'lstm' or 'xgboost'")
        
        # Generate version ID if not provided
        if version_id is None:
            version_id = self._get_next_version(model_type)
        else:
            # Validate version format
            self._parse_version(version_id)
        
        # Check if version already exists
        if model_type in self.versions:
            existing = [v for v in self.versions[model_type] if v.version_id == version_id]
            if existing:
                raise ValueError(f"Version {version_id} already exists for {model_type}")
        
        # Create version
        version = ModelVersion(
            version_id=version_id,
            model_type=model_type,
            created_at=datetime.now(),
            metrics=metrics,
            file_path=file_path,
            is_active=False,
        )
        
        # Add to versions
        if model_type not in self.versions:
            self.versions[model_type] = []
        
        self.versions[model_type].append(version)
        
        # Sort by version number
        self.versions[model_type].sort(
            key=lambda v: self._parse_version(v.version_id)
        )
        
        # Save to storage
        self._save_versions()
        
        logger.info(f"Registered {model_type} model version {version_id}")
        
        return version
    
    def get_active_model(self, model_type: str) -> Optional[ModelVersion]:
        """
        Get the currently active model version.
        
        Args:
            model_type: Model type (lstm, xgboost)
            
        Returns:
            Active ModelVersion or None
        """
        if model_type not in self.active_versions:
            return None
        
        version_id = self.active_versions[model_type]
        
        if model_type not in self.versions:
            return None
        
        for version in self.versions[model_type]:
            if version.version_id == version_id:
                return version
        
        return None
    
    def activate_model(self, version_id: str) -> bool:
        """
        Activate a specific model version.
        
        Args:
            version_id: Version ID to activate
            
        Returns:
            True if activation successful
        """
        # Find version
        for model_type, versions in self.versions.items():
            for version in versions:
                if version.version_id == version_id:
                    # Deactivate current active version
                    current_active = self.get_active_model(model_type)
                    if current_active:
                        current_active.is_active = False
                    
                    # Activate new version
                    version.is_active = True
                    self.active_versions[model_type] = version_id
                    
                    # Save
                    self._save_versions()
                    
                    logger.info(f"Activated {model_type} model version {version_id}")
                    return True
        
        logger.warning(f"Version {version_id} not found")
        return False
    
    def rollback_model(self, model_type: str, steps: int = 1) -> Optional[ModelVersion]:
        """
        Rollback to a previous model version.
        
        Args:
            model_type: Model type (lstm, xgboost)
            steps: Number of versions to rollback (default: 1)
            
        Returns:
            ModelVersion after rollback or None
        """
        if model_type not in self.versions or not self.versions[model_type]:
            logger.warning(f"No versions found for {model_type}")
            return None
        
        versions = self.versions[model_type]
        
        # Find current active version index
        current_active = self.get_active_model(model_type)
        if not current_active:
            logger.warning(f"No active version for {model_type}")
            return None
        
        current_idx = None
        for idx, v in enumerate(versions):
            if v.version_id == current_active.version_id:
                current_idx = idx
                break
        
        if current_idx is None:
            logger.warning(f"Active version not found in version list")
            return None
        
        # Calculate rollback index
        rollback_idx = current_idx - steps
        
        if rollback_idx < 0:
            logger.warning(f"Cannot rollback {steps} steps from current position")
            return None
        
        # Activate rollback version
        rollback_version = versions[rollback_idx]
        
        if self.activate_model(rollback_version.version_id):
            logger.info(f"Rolled back {model_type} to version {rollback_version.version_id}")
            return rollback_version
        
        return None
    
    def list_versions(self, model_type: str, limit: int = 10) -> List[ModelVersion]:
        """
        List model versions.
        
        Args:
            model_type: Model type (lstm, xgboost)
            limit: Maximum number of versions to return
            
        Returns:
            List of ModelVersion objects (most recent first)
        """
        if model_type not in self.versions:
            return []
        
        # Return most recent versions first
        versions = sorted(
            self.versions[model_type],
            key=lambda v: self._parse_version(v.version_id),
            reverse=True
        )
        
        return versions[:limit]
    
    def compare_versions(
        self,
        version_id1: str,
        version_id2: str
    ) -> Optional[VersionComparison]:
        """
        Compare two model versions.
        
        Args:
            version_id1: First version ID
            version_id2: Second version ID
            
        Returns:
            VersionComparison or None if versions not found
        """
        # Find both versions
        version1 = None
        version2 = None
        
        for model_type, versions in self.versions.items():
            for v in versions:
                if v.version_id == version_id1:
                    version1 = v
                if v.version_id == version_id2:
                    version2 = v
        
        if not version1 or not version2:
            logger.warning(f"One or both versions not found: {version_id1}, {version_id2}")
            return None
        
        # Calculate metrics differences
        metrics_diff = {}
        improvement_pct = {}
        
        all_metrics = set(version1.metrics.keys()) | set(version2.metrics.keys())
        
        for metric in all_metrics:
            val1 = version1.metrics.get(metric, 0)
            val2 = version2.metrics.get(metric, 0)
            
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                diff = val2 - val1
                metrics_diff[metric] = diff
                
                # Calculate percentage improvement
                if val1 != 0:
                    improvement_pct[metric] = (diff / abs(val1)) * 100
                else:
                    improvement_pct[metric] = 0.0
        
        # Determine winner based on accuracy (if available)
        winner = None
        if "accuracy" in metrics_diff:
            if metrics_diff["accuracy"] > 0:
                winner = version_id2
            elif metrics_diff["accuracy"] < 0:
                winner = version_id1
        
        return VersionComparison(
            version_id_1=version_id1,
            version_id_2=version_id2,
            metrics_diff=metrics_diff,
            winner=winner,
            improvement_pct=improvement_pct,
        )
    
    def get_version(self, version_id: str) -> Optional[ModelVersion]:
        """
        Get a specific version by ID.
        
        Args:
            version_id: Version ID
            
        Returns:
            ModelVersion or None
        """
        for model_type, versions in self.versions.items():
            for version in versions:
                if version.version_id == version_id:
                    return version
        
        return None
    
    def delete_version(self, version_id: str) -> bool:
        """
        Delete a model version.
        
        Args:
            version_id: Version ID to delete
            
        Returns:
            True if deletion successful
        """
        for model_type, versions in self.versions.items():
            for idx, version in enumerate(versions):
                if version.version_id == version_id:
                    # Cannot delete active version
                    if version.is_active:
                        logger.warning(f"Cannot delete active version {version_id}")
                        return False
                    
                    # Delete version
                    del versions[idx]
                    self._save_versions()
                    
                    logger.info(f"Deleted version {version_id}")
                    return True
        
        logger.warning(f"Version {version_id} not found")
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get versioning system statistics.
        
        Returns:
            Dictionary with statistics
        """
        stats = {
            "total_versions": sum(len(v) for v in self.versions.values()),
            "model_types": {},
        }
        
        for model_type, versions in self.versions.items():
            stats["model_types"][model_type] = {
                "count": len(versions),
                "active_version": self.active_versions.get(model_type),
                "latest_version": versions[-1].version_id if versions else None,
            }
        
        return stats
