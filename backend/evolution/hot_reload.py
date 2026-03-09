"""
Hot Reload Manager - TASK-026

Orchestrates model validation, versioning, and hot reload in RAM.
Provides seamless model updates without interrupting predictions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
import logging
import asyncio
from pathlib import Path

from .model_validation import ModelValidator, ValidationConfig, ValidationResult
from .model_versioning import ModelVersioningSystem, ModelVersion

logger = logging.getLogger(__name__)


@dataclass
class HotReloadConfig:
    """Configuration for hot reload manager."""
    
    # Validation settings
    validation_hours: int = 3
    min_profit_threshold: float = 0.0
    min_accuracy_threshold: float = 0.70
    
    # Model paths
    lstm_model_dir: str = "checkpoints"
    xgb_model_dir: str = "checkpoints"
    
    # Versioning
    versioning_storage: str = "checkpoints/versions.json"
    
    # Safety
    auto_rollback_on_failure: bool = True
    max_reload_attempts: int = 3
    cooldown_seconds: int = 300  # 5 minutes between reloads


@dataclass
class ReloadResult:
    """Result of a hot reload operation."""
    
    success: bool
    timestamp: datetime
    
    # Model info
    lstm_version: Optional[str] = None
    xgb_version: Optional[str] = None
    
    # Validation results
    validation_result: Optional[ValidationResult] = None
    
    # Timing
    validation_time_ms: float = 0.0
    reload_time_ms: float = 0.0
    total_time_ms: float = 0.0
    
    # Error handling
    error_message: Optional[str] = None
    rollback_performed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
            "lstm_version": self.lstm_version,
            "xgb_version": self.xgb_version,
            "validation_result": self.validation_result.to_dict() if self.validation_result else None,
            "validation_time_ms": self.validation_time_ms,
            "reload_time_ms": self.reload_time_ms,
            "total_time_ms": self.total_time_ms,
            "error_message": self.error_message,
            "rollback_performed": self.rollback_performed,
        }


class HotReloadManager:
    """
    Manages model hot reload with validation and versioning.
    
    Workflow:
    1. Validate new model on 3h historical data
    2. If validation passes, register new version
    3. Send reload command to inference worker
    4. Monitor reload success
    5. Rollback on failure if configured
    
    Usage:
        manager = HotReloadManager(config, inference_engine)
        
        # Validate and reload
        result = await manager.validate_and_reload(
            lstm_model_path="checkpoints/new_model.pt",
            xgb_model_path="checkpoints/new_xgb.json",
        )
    """
    
    def __init__(
        self,
        config: HotReloadConfig,
        inference_engine: Optional[Any] = None,
    ):
        self.config = config
        self.inference_engine = inference_engine
        
        # Initialize components
        self.validator = ModelValidator(
            config=ValidationConfig(
                validation_hours=config.validation_hours,
                min_profit_threshold=config.min_profit_threshold,
                min_accuracy_threshold=config.min_accuracy_threshold,
            )
        )
        
        self.versioning = ModelVersioningSystem(
            storage_path=config.versioning_storage
        )
        
        # State
        self.reload_history: List[ReloadResult] = []
        self.last_reload_time: Optional[datetime] = None
        self.reload_attempts: int = 0
    
    async def validate_model(
        self,
        lstm_model_path: Optional[str] = None,
        xgb_model_path: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate model on historical data.
        
        Args:
            lstm_model_path: Path to LSTM model (optional)
            xgb_model_path: Path to XGBoost model (optional)
            
        Returns:
            ValidationResult with performance metrics
        """
        logger.info("Starting model validation...")
        
        # Load models if paths provided
        lstm_model = None
        xgb_model = None
        
        if lstm_model_path and Path(lstm_model_path).exists():
            try:
                import torch
                from backend.models.lstm_model import RectangleLSTM, RectangleLSTMConfig
                
                checkpoint = torch.load(lstm_model_path, map_location='cpu')
                config = RectangleLSTMConfig(**checkpoint.get('config', {}))
                lstm_model = RectangleLSTM(config)
                lstm_model.load_state_dict(checkpoint['model_state_dict'])
                lstm_model.eval()
                
                logger.info(f"Loaded LSTM model from {lstm_model_path}")
            except Exception as e:
                logger.error(f"Failed to load LSTM model: {e}")
        
        if xgb_model_path and Path(xgb_model_path).exists():
            try:
                import xgboost as xgb
                
                xgb_model = xgb.XGBClassifier()
                xgb_model.load_model(xgb_model_path)
                
                logger.info(f"Loaded XGBoost model from {xgb_model_path}")
            except Exception as e:
                logger.error(f"Failed to load XGBoost model: {e}")
        
        # Run validation
        result = self.validator.validate_model(
            lstm_model=lstm_model,
            xgb_model=xgb_model,
            hours=self.config.validation_hours,
        )
        
        return result
    
    def register_new_version(
        self,
        model_type: str,
        file_path: str,
        metrics: Dict[str, Any],
    ) -> ModelVersion:
        """
        Register a new model version.
        
        Args:
            model_type: "lstm" or "xgboost"
            file_path: Path to model file
            metrics: Model metrics
            
        Returns:
            Created ModelVersion
        """
        version = self.versioning.register_model(
            model_type=model_type,
            file_path=file_path,
            metrics=metrics,
        )
        
        logger.info(f"Registered {model_type} version {version.version_id}")
        
        return version
    
    async def reload_inference_worker(
        self,
        lstm_version: Optional[str] = None,
        xgb_version: Optional[str] = None,
    ) -> bool:
        """
        Send reload command to inference worker.
        
        Args:
            lstm_version: LSTM version to load
            xgb_version: XGBoost version to load
            
        Returns:
            True if reload successful
        """
        if not self.inference_engine:
            logger.warning("No inference engine configured")
            return False
        
        if not self.inference_engine.is_running:
            logger.warning("Inference engine not running")
            return False
        
        logger.info(f"Sending reload command to inference worker...")
        
        # Get model paths from versions
        lstm_path = None
        xgb_path = None
        
        if lstm_version:
            version = self.versioning.get_version(lstm_version)
            if version:
                lstm_path = version.file_path
        
        if xgb_version:
            version = self.versioning.get_version(xgb_version)
            if version:
                xgb_path = version.file_path
        
        # Send reload command
        try:
            success = await self.inference_engine.reload_models(
                lstm_model_path=lstm_path,
                xgb_model_path=xgb_path,
            )
            
            if success:
                logger.info("Models reloaded successfully in inference worker")
            else:
                logger.error("Failed to reload models in inference worker")
            
            return success
            
        except Exception as e:
            logger.error(f"Reload command failed: {e}")
            return False
    
    async def validate_and_reload(
        self,
        lstm_model_path: Optional[str] = None,
        xgb_model_path: Optional[str] = None,
        skip_validation: bool = False,
    ) -> ReloadResult:
        """
        Validate models and perform hot reload if validation passes.
        
        Args:
            lstm_model_path: Path to new LSTM model
            xgb_model_path: Path to new XGBoost model
            skip_validation: Skip validation (dangerous, for testing only)
            
        Returns:
            ReloadResult with outcome
        """
        start_time = asyncio.get_event_loop().time()
        
        logger.info("=" * 60)
        logger.info("Starting hot reload process...")
        logger.info("=" * 60)
        
        result = ReloadResult(
            success=False,
            timestamp=datetime.now(),
        )
        
        try:
            # Check cooldown
            if self.last_reload_time:
                elapsed = (datetime.now() - self.last_reload_time).total_seconds()
                if elapsed < self.config.cooldown_seconds:
                    result.error_message = f"Cooldown active: {elapsed:.0f}s < {self.config.cooldown_seconds}s"
                    logger.warning(result.error_message)
                    return result
            
            # Check max attempts
            if self.reload_attempts >= self.config.max_reload_attempts:
                result.error_message = f"Max reload attempts reached: {self.reload_attempts}"
                logger.warning(result.error_message)
                return result
            
            # Phase 1: Validation
            validation_start = asyncio.get_event_loop().time()
            
            if not skip_validation:
                logger.info("[Phase 1] Validating models on 3h historical data...")
                
                validation_result = await self.validate_model(
                    lstm_model_path=lstm_model_path,
                    xgb_model_path=xgb_model_path,
                )
                
                result.validation_result = validation_result
                result.validation_time_ms = (asyncio.get_event_loop().time() - validation_start) * 1000
                
                if not validation_result.success:
                    result.error_message = f"Validation failed: {validation_result.error_message}"
                    logger.error(result.error_message)
                    return result
                
                logger.info(f"Validation passed: profit={validation_result.total_profit:.4f}, "
                           f"accuracy={validation_result.accuracy:.2%}")
            else:
                logger.warning("[Phase 1] SKIPPED - Validation disabled")
            
            # Phase 2: Register versions
            logger.info("[Phase 2] Registering new model versions...")
            
            if lstm_model_path:
                # Extract metrics from validation
                metrics = {}
                if result.validation_result:
                    metrics = {
                        "accuracy": result.validation_result.lstm_accuracy,
                        "validation_profit": result.validation_result.total_profit,
                        "validation_hours": result.validation_result.validation_hours,
                    }
                
                lstm_version = self.register_new_version(
                    model_type="lstm",
                    file_path=lstm_model_path,
                    metrics=metrics,
                )
                result.lstm_version = lstm_version.version_id
            
            if xgb_model_path:
                metrics = {}
                if result.validation_result:
                    metrics = {
                        "accuracy": result.validation_result.xgb_precision,
                        "validation_profit": result.validation_result.total_profit,
                        "validation_hours": result.validation_result.validation_hours,
                    }
                
                xgb_version = self.register_new_version(
                    model_type="xgboost",
                    file_path=xgb_model_path,
                    metrics=metrics,
                )
                result.xgb_version = xgb_version.version_id
            
            # Phase 3: Hot reload
            logger.info("[Phase 3] Performing hot reload in RAM...")
            
            reload_start = asyncio.get_event_loop().time()
            
            reload_success = await self.reload_inference_worker(
                lstm_version=result.lstm_version,
                xgb_version=result.xgb_version,
            )
            
            result.reload_time_ms = (asyncio.get_event_loop().time() - reload_start) * 1000
            
            if not reload_success:
                result.error_message = "Failed to reload models in inference worker"
                logger.error(result.error_message)
                
                # Rollback if configured
                if self.config.auto_rollback_on_failure:
                    logger.info("Performing automatic rollback...")
                    await self._perform_rollback()
                    result.rollback_performed = True
                
                return result
            
            # Phase 4: Activate versions
            logger.info("[Phase 4] Activating new model versions...")
            
            if result.lstm_version:
                self.versioning.activate_model(result.lstm_version)
            
            if result.xgb_version:
                self.versioning.activate_model(result.xgb_version)
            
            # Success!
            result.success = True
            self.last_reload_time = datetime.now()
            self.reload_attempts = 0
            
            result.total_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            logger.info("=" * 60)
            logger.info("Hot reload completed successfully!")
            logger.info(f"  LSTM: {result.lstm_version}")
            logger.info(f"  XGBoost: {result.xgb_version}")
            logger.info(f"  Total time: {result.total_time_ms:.2f}ms")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Hot reload failed: {e}", exc_info=True)
            result.error_message = str(e)
            
            # Rollback if configured
            if self.config.auto_rollback_on_failure:
                logger.info("Performing automatic rollback...")
                await self._perform_rollback()
                result.rollback_performed = True
        
        finally:
            # Store in history
            self.reload_history.append(result)
            
            # Increment attempts on failure
            if not result.success:
                self.reload_attempts += 1
        
        return result
    
    async def _perform_rollback(self):
        """Perform rollback to previous model versions."""
        logger.info("Rolling back to previous model versions...")
        
        # Rollback LSTM
        if "lstm" in self.versioning.active_versions:
            previous = self.versioning.rollback_model("lstm", steps=1)
            if previous:
                logger.info(f"Rolled back LSTM to {previous.version_id}")
        
        # Rollback XGBoost
        if "xgboost" in self.versioning.active_versions:
            previous = self.versioning.rollback_model("xgboost", steps=1)
            if previous:
                logger.info(f"Rolled back XGBoost to {previous.version_id}")
        
        # Reload previous versions in worker
        if self.inference_engine and self.inference_engine.is_running:
            await self.reload_inference_worker(
                lstm_version=self.versioning.active_versions.get("lstm"),
                xgb_version=self.versioning.active_versions.get("xgboost"),
            )
    
    def get_status(self) -> Dict[str, Any]:
        """Get hot reload manager status."""
        return {
            "last_reload_time": self.last_reload_time.isoformat() if self.last_reload_time else None,
            "reload_attempts": self.reload_attempts,
            "cooldown_seconds": self.config.cooldown_seconds,
            "max_reload_attempts": self.config.max_reload_attempts,
            "auto_rollback": self.config.auto_rollback_on_failure,
            "validation_hours": self.config.validation_hours,
            "reload_history_count": len(self.reload_history),
            "versioning_stats": self.versioning.get_statistics(),
        }
    
    def reset_attempts(self):
        """Reset reload attempts counter."""
        self.reload_attempts = 0
        logger.info("Reload attempts counter reset")
