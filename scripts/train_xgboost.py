#!/usr/bin/env python3
"""
CLI Script for Training LeadXGBoost Model

This script provides a command-line interface for training the XGBoost
trigger model for detecting leading micro-spikes in Binance data.

Usage:
    python scripts/train_xgboost.py [options]

Examples:
    # Train with mock data
    python scripts/train_xgboost.py

    # Train with custom parameters
    python scripts/train_xgboost.py --n-estimators 200 --max-depth 8 --threshold 0.9

    # Train with real data
    python scripts/train_xgboost.py --data path/to/data.csv
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np

from backend.models.xgboost_model import (
    LeadXGBoost,
    LeadXGBoostConfig,
    LeadXGBoostTrainer,
    generate_mock_data,
    train_xgboost_model,
)


def setup_logging(verbose: bool = True) -> logging.Logger:
    """Setup logging configuration."""
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Train LeadXGBoost model for micro-spike detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Train with mock data
  %(prog)s --data market_data.csv       # Train with custom data
  %(prog)s --n-estimators 200           # Use 200 trees
  %(prog)s --threshold 0.9              # Use 0.9 confidence threshold
  %(prog)s --output models/             # Save to custom directory
        """,
    )

    # Data arguments
    parser.add_argument(
        "--data",
        type=str,
        default=None,
        help="Path to training data (CSV). If not provided, uses mock data.",
    )
    parser.add_argument(
        "--label-column",
        type=str,
        default="label",
        help="Name of the label column in the data (default: label)",
    )

    # Model hyperparameters
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=100,
        help="Number of boosting rounds (default: 100)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=6,
        help="Maximum tree depth (default: 6)",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.1,
        help="Learning rate / eta (default: 0.1)",
    )
    parser.add_argument(
        "--min-child-weight",
        type=float,
        default=1.0,
        help="Minimum sum of instance weight in a child (default: 1.0)",
    )
    parser.add_argument(
        "--gamma",
        type=float,
        default=0.0,
        help="Minimum loss reduction for split (default: 0.0)",
    )
    parser.add_argument(
        "--subsample",
        type=float,
        default=0.8,
        help="Subsample ratio of training instances (default: 0.8)",
    )
    parser.add_argument(
        "--colsample-bytree",
        type=float,
        default=0.8,
        help="Subsample ratio of columns (default: 0.8)",
    )

    # Signal generation
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Confidence threshold for signal generation (default: 0.85)",
    )

    # Training options
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Proportion of data for testing (default: 0.2)",
    )
    parser.add_argument(
        "--val-size",
        type=float,
        default=0.1,
        help="Proportion of training data for validation (default: 0.1)",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )

    # Output options
    parser.add_argument(
        "--output",
        type=str,
        default="checkpoints",
        help="Output directory for model and results (default: checkpoints)",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="lead_xgboost",
        help="Name for the saved model (default: lead_xgboost)",
    )

    # Mock data options
    parser.add_argument(
        "--mock-samples",
        type=int,
        default=10000,
        help="Number of mock samples to generate (default: 10000)",
    )
    parser.add_argument(
        "--mock-positive-ratio",
        type=float,
        default=0.15,
        help="Ratio of positive samples in mock data (default: 0.15)",
    )

    # Verbosity
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=True,
        help="Enable verbose output (default: True)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress output",
    )

    return parser.parse_args()


def load_data(args: argparse.Namespace, logger: logging.Logger) -> pd.DataFrame:
    """Load training data from file or generate mock data."""
    if args.data:
        logger.info(f"Loading data from {args.data}")
        data = pd.read_csv(args.data)

        # Validate required columns
        config = LeadXGBoostConfig()
        required_cols = list(config.feature_names) + [args.label_column]
        missing_cols = [col for col in required_cols if col not in data.columns]

        if missing_cols:
            logger.error(f"Missing required columns: {missing_cols}")
            sys.exit(1)

        logger.info(f"Loaded {len(data)} samples")
        return data
    else:
        logger.info(f"Generating mock data with {args.mock_samples} samples")
        data = generate_mock_data(
            n_samples=args.mock_samples,
            random_state=args.random_state,
            positive_ratio=args.mock_positive_ratio,
        )
        logger.info(f"Generated {len(data)} samples")
        logger.info(f"Positive ratio: {data['label'].mean():.2%}")
        return data


def print_metrics(metrics: dict, threshold: float, logger: logging.Logger) -> None:
    """Print evaluation metrics in a formatted way."""
    logger.info("\n" + "=" * 50)
    logger.info("EVALUATION METRICS")
    logger.info("=" * 50)

    # Overall metrics
    logger.info("\nOverall Performance:")
    logger.info(f"  Precision:     {metrics['precision']:.4f}")
    logger.info(f"  Recall:        {metrics['recall']:.4f}")
    logger.info(f"  F1 Score:      {metrics['f1']:.4f}")
    logger.info(f"  AUC-ROC:       {metrics['auc']:.4f}")
    logger.info(f"  Log Loss:      {metrics['logloss']:.4f}")

    # Confusion matrix
    if 'confusion_matrix' in metrics:
        cm = metrics['confusion_matrix']
        logger.info("\nConfusion Matrix:")
        logger.info(f"  TN: {cm['tn']:6d}  |  FP: {cm['fp']:6d}")
        logger.info(f"  FN: {cm['fn']:6d}  |  TP: {cm['tp']:6d}")

    # High confidence metrics
    if 'high_confidence_precision' in metrics:
        logger.info(f"\nHigh Confidence Signals (>{threshold}):")
        logger.info(f"  Count:         {metrics['high_confidence_count']}")
        logger.info(f"  Precision:     {metrics['high_confidence_precision']:.4f}")
        logger.info(f"  Recall:        {metrics['high_confidence_recall']:.4f}")

    logger.info("=" * 50)


def main() -> int:
    """Main entry point."""
    args = parse_args()
    verbose = args.verbose and not args.quiet
    logger = setup_logging(verbose)

    # Print header
    if verbose:
        logger.info("=" * 60)
        logger.info("LeadXGBoost Training Script")
        logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

    # Create configuration
    config = LeadXGBoostConfig(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        min_child_weight=args.min_child_weight,
        gamma=args.gamma,
        subsample=args.subsample,
        colsample_bytree=args.colsample_bytree,
        confidence_threshold=args.threshold,
        random_state=args.random_state,
    )

    if verbose:
        logger.info("\nModel Configuration:")
        logger.info(f"  n_estimators:       {config.n_estimators}")
        logger.info(f"  max_depth:          {config.max_depth}")
        logger.info(f"  learning_rate:      {config.learning_rate}")
        logger.info(f"  confidence_threshold: {config.confidence_threshold}")

    # Load data
    data = load_data(args, logger)

    # Initialize trainer
    output_dir = Path(args.output)
    trainer = LeadXGBoostTrainer(config, output_dir=output_dir)

    # Prepare data splits
    if verbose:
        logger.info("\nPreparing data splits...")

    X_train, X_test, X_val, y_train, y_test, y_val = trainer.prepare_training_data(
        data,
        label_column=args.label_column,
        test_size=args.test_size,
        val_size=args.val_size,
    )

    if verbose:
        logger.info(f"  Training samples:   {len(X_train)}")
        logger.info(f"  Validation samples: {len(X_val)}")
        logger.info(f"  Test samples:       {len(X_test)}")

    # Train model
    if verbose:
        logger.info("\nTraining model...")

    train_metrics = trainer.train(
        X_train, y_train, X_val, y_val, verbose=verbose
    )

    if verbose:
        logger.info("\nTraining Metrics:")
        logger.info(f"  AUC: {train_metrics['auc']:.4f}")
        logger.info(f"  Log Loss: {train_metrics['logloss']:.4f}")

    # Evaluate on test set
    if verbose:
        logger.info("\nEvaluating on test set...")

    test_metrics = trainer.evaluate(X_test, y_test)

    # Print metrics
    print_metrics(test_metrics, config.confidence_threshold, logger)

    # Save model
    model_path = trainer.save_model(args.model_name)

    if verbose:
        logger.info(f"\nModel saved to: {model_path}")

    # Feature importance
    if verbose and trainer.model:
        logger.info("\nTop 5 Feature Importance:")
        importance = trainer.model.get_feature_importance()
        sorted_importance = sorted(
            importance.items(), key=lambda x: x[1], reverse=True
        )[:5]
        for name, score in sorted_importance:
            logger.info(f"  {name:25s}: {score:.4f}")

    # Final summary
    if verbose:
        logger.info("\n" + "=" * 60)
        logger.info("TRAINING COMPLETE")
        logger.info(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

    # Return success
    return 0


if __name__ == "__main__":
    sys.exit(main())
