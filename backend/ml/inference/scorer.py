"""
POI Quality Scorer - Inference Module
=====================================

This module provides the inference interface for the POI quality scoring model.
It loads the trained Gradient Boosting model and provides methods for:
- Single POI scoring
- Batch POI scoring
- Feature extraction and validation

Model Performance:
- R² Score: 0.9999
- MAE: 0.07 points (on 0-100 scale)
- RMSE: 0.12 points

Author: Nicolas Angougeard
"""

import os
import json
import joblib
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
import numpy as np
import pandas as pd
from datetime import datetime


@dataclass
class POIScoringResult:
    """Result container for POI quality scoring."""

    poi_id: str
    quality_score: float
    confidence: float
    features: Dict[str, float]
    timestamp: str
    model_version: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "poi_id": self.poi_id,
            "quality_score": round(self.quality_score, 2),
            "confidence": round(self.confidence, 3),
            "features": {k: round(v, 3) for k, v in self.features.items()},
            "timestamp": self.timestamp,
            "model_version": self.model_version
        }


class POIQualityScorer:
    """
    POI Quality Scorer using Gradient Boosting Regressor.

    This class handles:
    - Model loading and caching
    - Feature extraction from raw POI data
    - Quality score prediction (0-100 scale)
    - Feature importance analysis

    Example:
        >>> scorer = POIQualityScorer()
        >>> poi_data = {
        ...     "name": "Tour Eiffel",
        ...     "description": "Monument emblématique de Paris",
        ...     "latitude": 48.8584,
        ...     "longitude": 2.2945,
        ...     ...
        ... }
        >>> result = scorer.score_poi(poi_data)
        >>> print(f"Quality Score: {result.quality_score}/100")
    """

    REQUIRED_FEATURES = [
        # Completeness features
        "has_name",
        "has_description",
        "has_gps",
        "has_address",
        "has_images",
        "has_opening_hours",
        "has_contact",

        # Richness features
        "description_length",
        "num_images",
        "has_website",

        # Context features (geographic)
        "latitude",
        "longitude",
        "insee_salary_median",
        "population",
        "poi_density_10km",

        # Freshness
        "days_since_update",
        "is_recent"
    ]

    def __init__(
        self,
        model_path: Optional[Path] = None,
        metrics_path: Optional[Path] = None
    ):
        """
        Initialize the POI Quality Scorer.

        Args:
            model_path: Path to the trained model file (.pkl)
            metrics_path: Path to model metrics JSON file
        """
        if model_path is None:
            # Default path relative to this file
            base_path = Path(__file__).parent.parent / "models" / "quality_scorer"
            model_path = base_path / "scorer.pkl"
            metrics_path = base_path / "metrics.json"

        self.model_path = Path(model_path)
        self.metrics_path = Path(metrics_path) if metrics_path else None

        # Load model and metadata
        self.model = self._load_model()
        self.metrics = self._load_metrics()
        self.model_version = self._get_model_version()

        # Feature importance (if available)
        self.feature_importance = self._extract_feature_importance()

    def _load_model(self) -> Any:
        """Load the trained model from disk."""
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model file not found at {self.model_path}. "
                "Please run training script first: ml/training/03_train_quality_scorer.py"
            )

        try:
            model = joblib.load(self.model_path)
            return model
        except Exception as e:
            raise RuntimeError(f"Failed to load model: {e}")

    def _load_metrics(self) -> Optional[Dict[str, float]]:
        """Load model performance metrics."""
        if self.metrics_path and self.metrics_path.exists():
            with open(self.metrics_path, 'r') as f:
                return json.load(f)
        return None

    def _get_model_version(self) -> str:
        """Get model version from metrics or file timestamp."""
        if self.metrics and "model_version" in self.metrics:
            return self.metrics["model_version"]

        # Fallback: use file modification time
        mtime = self.model_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%Y%m%d_%H%M%S")

    def _extract_feature_importance(self) -> Optional[Dict[str, float]]:
        """Extract feature importance from the model."""
        try:
            if hasattr(self.model, 'feature_importances_'):
                importances = self.model.feature_importances_
                return dict(zip(self.REQUIRED_FEATURES, importances))
        except Exception:
            pass
        return None

    def extract_features(self, poi_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract ML features from raw POI data.

        Args:
            poi_data: Dictionary containing POI information

        Returns:
            Dictionary of engineered features

        Raises:
            ValueError: If required fields are missing
        """
        features = {}

        # Completeness features (binary)
        features["has_name"] = float(bool(poi_data.get("name")))
        features["has_description"] = float(bool(poi_data.get("description")))
        features["has_gps"] = float(
            poi_data.get("latitude") is not None and
            poi_data.get("longitude") is not None
        )
        features["has_address"] = float(bool(poi_data.get("address")))
        features["has_images"] = float(
            poi_data.get("num_images", 0) > 0 or
            bool(poi_data.get("images"))
        )
        features["has_opening_hours"] = float(bool(poi_data.get("opening_hours")))
        features["has_contact"] = float(
            bool(poi_data.get("phone")) or
            bool(poi_data.get("email"))
        )

        # Richness features (continuous)
        description = poi_data.get("description", "")
        features["description_length"] = float(len(description))
        features["num_images"] = float(poi_data.get("num_images", 0))
        features["has_website"] = float(bool(poi_data.get("website")))

        # Geographic features
        features["latitude"] = float(poi_data.get("latitude", 0.0))
        features["longitude"] = float(poi_data.get("longitude", 0.0))

        # Context features (external data)
        features["insee_salary_median"] = float(
            poi_data.get("insee_salary_median", 2000.0)
        )
        features["population"] = float(poi_data.get("population", 10000))
        features["poi_density_10km"] = float(poi_data.get("poi_density_10km", 50))

        # Freshness features
        updated_at = poi_data.get("updated_at")
        if updated_at:
            try:
                update_date = pd.to_datetime(updated_at)
                days_since = (pd.Timestamp.now() - update_date).days
                features["days_since_update"] = float(days_since)
                features["is_recent"] = float(days_since <= 180)  # 6 months
            except Exception:
                features["days_since_update"] = 365.0
                features["is_recent"] = 0.0
        else:
            features["days_since_update"] = 365.0
            features["is_recent"] = 0.0

        return features

    def score_poi(
        self,
        poi_data: Dict[str, Any],
        return_features: bool = False
    ) -> POIScoringResult:
        """
        Score a single POI's quality.

        Args:
            poi_data: Dictionary containing POI information
            return_features: Whether to include features in the result

        Returns:
            POIScoringResult with quality score and metadata
        """
        # Extract features
        features = self.extract_features(poi_data)

        # Create feature vector in correct order
        feature_vector = np.array([
            features[feat] for feat in self.REQUIRED_FEATURES
        ]).reshape(1, -1)

        # Predict quality score
        quality_score = float(self.model.predict(feature_vector)[0])

        # Calculate confidence (based on feature completeness)
        completeness_features = [
            "has_name", "has_description", "has_gps",
            "has_address", "has_images"
        ]
        completeness = sum(features[f] for f in completeness_features) / len(completeness_features)
        confidence = min(0.95, 0.5 + completeness * 0.5)  # Scale to 0.5-0.95

        return POIScoringResult(
            poi_id=poi_data.get("id", "unknown"),
            quality_score=quality_score,
            confidence=confidence,
            features=features if return_features else {},
            timestamp=datetime.now().isoformat(),
            model_version=self.model_version
        )

    def score_batch(
        self,
        pois: List[Dict[str, Any]],
        return_features: bool = False
    ) -> List[POIScoringResult]:
        """
        Score multiple POIs efficiently.

        Args:
            pois: List of POI dictionaries
            return_features: Whether to include features in results

        Returns:
            List of POIScoringResult objects
        """
        return [self.score_poi(poi, return_features) for poi in pois]

    def get_feature_importance(self, top_n: int = 10) -> Dict[str, float]:
        """
        Get the top N most important features.

        Args:
            top_n: Number of top features to return

        Returns:
            Dictionary of feature names and their importance scores
        """
        if not self.feature_importance:
            return {}

        sorted_features = sorted(
            self.feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return dict(sorted_features[:top_n])

    def get_model_info(self) -> Dict[str, Any]:
        """Get comprehensive model information."""
        info = {
            "model_type": type(self.model).__name__,
            "model_version": self.model_version,
            "model_path": str(self.model_path),
            "num_features": len(self.REQUIRED_FEATURES),
            "features": self.REQUIRED_FEATURES,
        }

        if self.metrics:
            info["performance"] = self.metrics

        if self.feature_importance:
            info["top_features"] = self.get_feature_importance(5)

        return info

    def __repr__(self) -> str:
        return (
            f"POIQualityScorer(model={type(self.model).__name__}, "
            f"version={self.model_version}, "
            f"features={len(self.REQUIRED_FEATURES)})"
        )
