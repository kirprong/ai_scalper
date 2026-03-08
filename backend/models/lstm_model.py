"""
RectangleLSTM Model for Golden Rectangle Detection

This module implements an LSTM neural network for detecting Golden Rectangle
patterns in market data. The model takes sequences of market features and
outputs a probability of Golden Rectangle presence.

Architecture:
- Input: (batch, seq_len=60, features=10)
- LSTM Layer 1: hidden_size=128
- LSTM Layer 2: hidden_size=64
- Dropout: 0.2
- Fully Connected: 64 -> 32 -> 1
- Output: Sigmoid probability
"""

from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any
import numpy as np

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader


@dataclass
class RectangleLSTMConfig:
    """Configuration for RectangleLSTM model."""
    
    # Input dimensions
    input_size: int = 10  # Number of features
    seq_len: int = 60  # Sequence length (bars)
    
    # LSTM architecture
    hidden_size_1: int = 128  # First LSTM layer hidden size
    hidden_size_2: int = 64  # Second LSTM layer hidden size
    num_layers: int = 2  # Number of LSTM layers
    dropout: float = 0.2  # Dropout rate
    
    # Fully connected layers
    fc_hidden_size: int = 32  # Hidden size of FC layer
    
    # Training configuration
    batch_size: int = 32
    learning_rate: float = 0.001
    epochs: int = 50
    
    # Feature names (for reference)
    feature_names: Tuple[str, ...] = (
        "price_normalized",
        "volume_normalized",
        "std_dev_price",
        "velocity",
        "order_book_imbalance",
        "taker_buy_sell_ratio",
        "distance_to_target",
        "hurst_exponent",
        "ema_crossings",
        "mean_reversion_score",
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "input_size": self.input_size,
            "seq_len": self.seq_len,
            "hidden_size_1": self.hidden_size_1,
            "hidden_size_2": self.hidden_size_2,
            "num_layers": self.num_layers,
            "dropout": self.dropout,
            "fc_hidden_size": self.fc_hidden_size,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "epochs": self.epochs,
            "feature_names": list(self.feature_names),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RectangleLSTMConfig":
        """Create config from dictionary."""
        return cls(
            input_size=data.get("input_size", 10),
            seq_len=data.get("seq_len", 60),
            hidden_size_1=data.get("hidden_size_1", 128),
            hidden_size_2=data.get("hidden_size_2", 64),
            num_layers=data.get("num_layers", 2),
            dropout=data.get("dropout", 0.2),
            fc_hidden_size=data.get("fc_hidden_size", 32),
            batch_size=data.get("batch_size", 32),
            learning_rate=data.get("learning_rate", 0.001),
            epochs=data.get("epochs", 50),
            feature_names=tuple(data.get("feature_names", (
                "price_normalized",
                "volume_normalized",
                "std_dev_price",
                "velocity",
                "order_book_imbalance",
                "taker_buy_sell_ratio",
                "distance_to_target",
                "hurst_exponent",
                "ema_crossings",
                "mean_reversion_score",
            ))),
        )


class RectangleLSTM(nn.Module):
    """
    LSTM model for Golden Rectangle detection.
    
    Architecture:
    - Input: (batch, seq_len=60, features=10)
    - LSTM Layer 1: hidden_size=128
    - LSTM Layer 2: hidden_size=64
    - Dropout: 0.2
    - Fully Connected: 64 -> 32 -> 1
    - Output: Sigmoid probability
    
    The model processes sequences of market data and outputs a probability
    that the sequence contains a Golden Rectangle pattern.
    """
    
    def __init__(self, config: Optional[RectangleLSTMConfig] = None):
        """
        Initialize the RectangleLSTM model.
        
        Args:
            config: Model configuration. If None, uses default config.
        """
        super().__init__()
        
        self.config = config or RectangleLSTMConfig()
        
        # First LSTM layer
        self.lstm1 = nn.LSTM(
            input_size=self.config.input_size,
            hidden_size=self.config.hidden_size_1,
            batch_first=True,
            bidirectional=False,
        )
        
        # Dropout after first LSTM layer
        self.dropout1 = nn.Dropout(self.config.dropout)
        
        # Second LSTM layer
        self.lstm2 = nn.LSTM(
            input_size=self.config.hidden_size_1,
            hidden_size=self.config.hidden_size_2,
            batch_first=True,
            bidirectional=False,
        )
        
        # Dropout after second LSTM layer
        self.dropout2 = nn.Dropout(self.config.dropout)
        
        # Fully connected layers
        self.fc1 = nn.Linear(self.config.hidden_size_2, self.config.fc_hidden_size)
        self.relu = nn.ReLU()
        self.dropout3 = nn.Dropout(self.config.dropout)
        self.fc2 = nn.Linear(self.config.fc_hidden_size, 1)
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize model weights using Xavier initialization."""
        for name, param in self.named_parameters():
            if 'weight_ih' in name:
                nn.init.xavier_uniform_(param.data)
            elif 'weight_hh' in name:
                nn.init.orthogonal_(param.data)
            elif 'bias' in name:
                param.data.fill_(0)
                # Set forget gate bias to 1 for better gradient flow
                if 'lstm' in name:
                    n = param.size(0)
                    param.data[n // 4:n // 2].fill_(1)
    
    def forward(
        self,
        x: torch.Tensor,
        hidden: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
    ) -> Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Forward pass through the model.
        
        Args:
            x: Input tensor of shape (batch, seq_len, features)
            hidden: Optional initial hidden state tuple (h_0, c_0)
        
        Returns:
            Tuple of (output probability, final hidden state)
        """
        batch_size = x.size(0)
        
        # Initialize hidden state if not provided
        if hidden is None:
            h1 = torch.zeros(1, batch_size, self.config.hidden_size_1, device=x.device)
            c1 = torch.zeros(1, batch_size, self.config.hidden_size_1, device=x.device)
        else:
            h1, c1 = hidden
        
        # First LSTM layer
        lstm1_out, (h1_n, c1_n) = self.lstm1(x, (h1, c1))
        lstm1_out = self.dropout1(lstm1_out)
        
        # Second LSTM layer
        h2 = torch.zeros(1, batch_size, self.config.hidden_size_2, device=x.device)
        c2 = torch.zeros(1, batch_size, self.config.hidden_size_2, device=x.device)
        lstm2_out, (h2_n, c2_n) = self.lstm2(lstm1_out, (h2, c2))
        lstm2_out = self.dropout2(lstm2_out)
        
        # Take the last output from the sequence
        last_output = lstm2_out[:, -1, :]  # (batch, hidden_size_2)
        
        # Fully connected layers
        fc1_out = self.fc1(last_output)
        fc1_out = self.relu(fc1_out)
        fc1_out = self.dropout3(fc1_out)
        
        # Output layer (logits)
        logits = self.fc2(fc1_out)
        
        # Return logits and final hidden state
        return logits, (h2_n, c2_n)
    
    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """
        Get probability predictions.
        
        Args:
            x: Input tensor of shape (batch, seq_len, features)
        
        Returns:
            Probability tensor of shape (batch, 1)
        """
        self.eval()
        with torch.no_grad():
            logits, _ = self.forward(x)
            probs = torch.sigmoid(logits)
        return probs
    
    def predict(self, x: torch.Tensor, threshold: float = 0.5) -> torch.Tensor:
        """
        Get binary predictions.
        
        Args:
            x: Input tensor of shape (batch, seq_len, features)
            threshold: Classification threshold
        
        Returns:
            Binary prediction tensor of shape (batch, 1)
        """
        probs = self.predict_proba(x)
        return (probs >= threshold).float()


class RectangleLSTMDataset(Dataset):
    """
    PyTorch Dataset for Golden Rectangle detection.
    
    Generates sequences of features from market data for training
    the LSTM model.
    """
    
    def __init__(
        self,
        features: np.ndarray,
        labels: np.ndarray,
        seq_len: int = 60,
        transform: Optional[Any] = None,
    ):
        """
        Initialize the dataset.
        
        Args:
            features: Feature array of shape (n_samples, n_features)
            labels: Label array of shape (n_samples,)
            seq_len: Sequence length for LSTM input
            transform: Optional transform to apply to features
        """
        self.features = features
        self.labels = labels
        self.seq_len = seq_len
        self.transform = transform
        
        # Validate inputs
        if len(features) != len(labels):
            raise ValueError(
                f"Features and labels must have same length. "
                f"Got features: {len(features)}, labels: {len(labels)}"
            )
        
        if len(features) < seq_len:
            raise ValueError(
                f"Not enough samples for sequence length. "
                f"Got {len(features)} samples, need at least {seq_len}"
            )
        
        # Calculate valid indices (where we can form a complete sequence)
        self.valid_indices = list(range(seq_len - 1, len(features)))
    
    def __len__(self) -> int:
        """Return the number of valid sequences."""
        return len(self.valid_indices)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Get a single sequence and its label.
        
        Args:
            idx: Index into valid_indices
        
        Returns:
            Tuple of (sequence tensor, label tensor)
        """
        # Get the actual end index
        end_idx = self.valid_indices[idx]
        start_idx = end_idx - self.seq_len + 1
        
        # Extract sequence
        sequence = self.features[start_idx:end_idx + 1]
        label = self.labels[end_idx]
        
        # Apply transform if provided
        if self.transform:
            sequence = self.transform(sequence)
        
        # Convert to tensors
        sequence_tensor = torch.FloatTensor(sequence)
        label_tensor = torch.FloatTensor([label])
        
        return sequence_tensor, label_tensor
    
    def get_sequence_indices(self) -> List[int]:
        """Return the indices that correspond to each sequence's label."""
        return self.valid_indices.copy()


def create_sequences(
    features: np.ndarray,
    labels: np.ndarray,
    seq_len: int = 60,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Create sequences from features for LSTM input.
    
    Args:
        features: Feature array of shape (n_samples, n_features)
        labels: Label array of shape (n_samples,)
        seq_len: Sequence length
    
    Returns:
        Tuple of (sequences, labels) where sequences has shape
        (n_sequences, seq_len, n_features)
    """
    n_samples = len(features)
    n_features = features.shape[1]
    
    # Calculate number of valid sequences
    n_sequences = n_samples - seq_len + 1
    
    if n_sequences <= 0:
        raise ValueError(
            f"Not enough samples ({n_samples}) for sequence length {seq_len}"
        )
    
    # Pre-allocate arrays
    sequences = np.zeros((n_sequences, seq_len, n_features), dtype=np.float32)
    sequence_labels = np.zeros(n_sequences, dtype=np.float32)
    
    # Create sequences
    for i in range(n_sequences):
        sequences[i] = features[i:i + seq_len]
        sequence_labels[i] = labels[i + seq_len - 1]
    
    return sequences, sequence_labels


def normalize_features(
    features: np.ndarray,
    method: str = "minmax",
    feature_ranges: Optional[Dict[str, Tuple[float, float]]] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Normalize features for LSTM input.
    
    Args:
        features: Feature array of shape (n_samples, n_features)
        method: Normalization method ('minmax', 'zscore', 'robust')
        feature_ranges: Optional dict of feature ranges for minmax
    
    Returns:
        Tuple of (normalized features, normalization params)
    """
    normalized = np.zeros_like(features)
    params = {"method": method, "params": {}}
    
    if method == "minmax":
        # Min-max normalization to [0, 1]
        min_vals = np.min(features, axis=0)
        max_vals = np.max(features, axis=0)
        range_vals = max_vals - min_vals
        range_vals[range_vals == 0] = 1  # Avoid division by zero
        
        normalized = (features - min_vals) / range_vals
        params["params"] = {
            "min": min_vals.tolist(),
            "max": max_vals.tolist(),
        }
    
    elif method == "zscore":
        # Z-score normalization
        mean_vals = np.mean(features, axis=0)
        std_vals = np.std(features, axis=0)
        std_vals[std_vals == 0] = 1  # Avoid division by zero
        
        normalized = (features - mean_vals) / std_vals
        params["params"] = {
            "mean": mean_vals.tolist(),
            "std": std_vals.tolist(),
        }
    
    elif method == "robust":
        # Robust normalization using median and IQR
        median_vals = np.median(features, axis=0)
        q1 = np.percentile(features, 25, axis=0)
        q3 = np.percentile(features, 75, axis=0)
        iqr = q3 - q1
        iqr[iqr == 0] = 1  # Avoid division by zero
        
        normalized = (features - median_vals) / iqr
        params["params"] = {
            "median": median_vals.tolist(),
            "iqr": iqr.tolist(),
        }
    
    else:
        raise ValueError(f"Unknown normalization method: {method}")
    
    return normalized, params


def apply_normalization(
    features: np.ndarray,
    norm_params: Dict[str, Any],
) -> np.ndarray:
    """
    Apply previously computed normalization parameters.
    
    Args:
        features: Feature array to normalize
        norm_params: Normalization parameters from normalize_features
    
    Returns:
        Normalized features
    """
    method = norm_params["method"]
    params = norm_params["params"]
    
    if method == "minmax":
        min_vals = np.array(params["min"])
        max_vals = np.array(params["max"])
        range_vals = max_vals - min_vals
        range_vals[range_vals == 0] = 1
        
        return (features - min_vals) / range_vals
    
    elif method == "zscore":
        mean_vals = np.array(params["mean"])
        std_vals = np.array(params["std"])
        std_vals[std_vals == 0] = 1
        
        return (features - mean_vals) / std_vals
    
    elif method == "robust":
        median_vals = np.array(params["median"])
        iqr = np.array(params["iqr"])
        iqr[iqr == 0] = 1
        
        return (features - median_vals) / iqr
    
    else:
        raise ValueError(f"Unknown normalization method: {method}")
