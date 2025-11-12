"""
Unit Tests for POI Quality Scorer
================================

Tests cover:
- Model loading and initialization
- Feature extraction logic
- Score prediction accuracy
- Error handling
- Edge cases

Author: Nicolas Angougeard
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from ml.inference.scorer import POIQualityScorer, POIScoringResult


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def sample_poi_complete():
    """Sample POI with complete information."""
    return {
        "id": "poi_001",
        "name": "Tour Eiffel",
        "description": "Monument emblématique de Paris construit pour l'Exposition universelle de 1889",
        "latitude": 48.8584,
        "longitude": 2.2945,
        "address": "5 Avenue Anatole France, 75007 Paris",
        "num_images": 25,
        "website": "https://www.toureiffel.paris",
        "opening_hours": "9:30-23:45",
        "phone": "+33 8 92 70 12 39",
        "insee_salary_median": 2800.0,
        "population": 2_165_423,
        "poi_density_10km": 1250,
        "updated_at": "2025-01-15"
    }


@pytest.fixture
def sample_poi_minimal():
    """Sample POI with minimal information."""
    return {
        "id": "poi_002",
        "name": "Small Cafe",
        "latitude": 48.8566,
        "longitude": 2.3522
    }


@pytest.fixture
def mock_model():
    """Mock ML model for testing."""
    model = Mock()
    model.predict.return_value = np.array([85.5])
    model.feature_importances_ = np.random.random(17)
    return model


# ============================================
# Test POIQualityScorer Initialization
# ============================================

def test_scorer_initialization_default_path():
    """Test that scorer initializes with default paths."""
    # Note: This will fail if model doesn't exist, which is expected
    with pytest.raises(FileNotFoundError):
        scorer = POIQualityScorer()


def test_scorer_initialization_custom_path(mock_model, tmp_path):
    """Test scorer initialization with custom model path."""
    model_path = tmp_path / "test_model.pkl"

    with patch('ml.inference.scorer.joblib.load', return_value=mock_model):
        scorer = POIQualityScorer(model_path=model_path)
        assert scorer.model is not None


# ============================================
# Test Feature Extraction
# ============================================

def test_extract_features_complete_poi(sample_poi_complete):
    """Test feature extraction with complete POI data."""
    scorer = POIQualityScorer.__new__(POIQualityScorer)
    features = scorer.extract_features(sample_poi_complete)

    # Check all required features are present
    assert len(features) == 17

    # Check completeness features (should be 1.0 for complete POI)
    assert features["has_name"] == 1.0
    assert features["has_description"] == 1.0
    assert features["has_gps"] == 1.0
    assert features["has_address"] == 1.0
    assert features["has_images"] == 1.0
    assert features["has_opening_hours"] == 1.0
    assert features["has_contact"] == 1.0

    # Check richness features
    assert features["description_length"] > 0
    assert features["num_images"] == 25.0
    assert features["has_website"] == 1.0

    # Check geographic features
    assert features["latitude"] == 48.8584
    assert features["longitude"] == 2.2945


def test_extract_features_minimal_poi(sample_poi_minimal):
    """Test feature extraction with minimal POI data."""
    scorer = POIQualityScorer.__new__(POIQualityScorer)
    features = scorer.extract_features(sample_poi_minimal)

    # Check completeness features (most should be 0.0)
    assert features["has_name"] == 1.0
    assert features["has_description"] == 0.0
    assert features["has_gps"] == 1.0
    assert features["has_address"] == 0.0
    assert features["has_images"] == 0.0

    # Check defaults are applied
    assert features["description_length"] == 0.0
    assert features["insee_salary_median"] == 2000.0  # default
    assert features["population"] == 10000  # default


def test_extract_features_freshness():
    """Test freshness feature calculation."""
    scorer = POIQualityScorer.__new__(POIQualityScorer)

    # Recent POI (updated 30 days ago)
    recent_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    poi_recent = {
        "id": "test",
        "updated_at": recent_date,
        "latitude": 48.0,
        "longitude": 2.0
    }
    features_recent = scorer.extract_features(poi_recent)
    assert features_recent["is_recent"] == 1.0
    assert features_recent["days_since_update"] < 100

    # Old POI (updated 1 year ago)
    old_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    poi_old = {
        "id": "test",
        "updated_at": old_date,
        "latitude": 48.0,
        "longitude": 2.0
    }
    features_old = scorer.extract_features(poi_old)
    assert features_old["is_recent"] == 0.0
    assert features_old["days_since_update"] > 300


# ============================================
# Test POI Scoring
# ============================================

@patch('ml.inference.scorer.joblib.load')
def test_score_poi_returns_valid_result(mock_load, mock_model, sample_poi_complete, tmp_path):
    """Test that score_poi returns a valid POIScoringResult."""
    mock_load.return_value = mock_model
    model_path = tmp_path / "test_model.pkl"

    scorer = POIQualityScorer(model_path=model_path)
    result = scorer.score_poi(sample_poi_complete)

    assert isinstance(result, POIScoringResult)
    assert result.poi_id == "poi_001"
    assert 0 <= result.quality_score <= 100
    assert 0 <= result.confidence <= 1.0
    assert result.model_version is not None


@patch('ml.inference.scorer.joblib.load')
def test_score_poi_with_features(mock_load, mock_model, sample_poi_complete, tmp_path):
    """Test scoring with feature return enabled."""
    mock_load.return_value = mock_model
    model_path = tmp_path / "test_model.pkl"

    scorer = POIQualityScorer(model_path=model_path)
    result = scorer.score_poi(sample_poi_complete, return_features=True)

    assert len(result.features) == 17
    assert "has_name" in result.features
    assert "quality_score" not in result.features  # score is not a feature


@patch('ml.inference.scorer.joblib.load')
def test_score_batch(mock_load, mock_model, sample_poi_complete, sample_poi_minimal, tmp_path):
    """Test batch scoring of multiple POIs."""
    mock_load.return_value = mock_model
    model_path = tmp_path / "test_model.pkl"

    scorer = POIQualityScorer(model_path=model_path)
    pois = [sample_poi_complete, sample_poi_minimal]
    results = scorer.score_batch(pois)

    assert len(results) == 2
    assert all(isinstance(r, POIScoringResult) for r in results)
    assert results[0].poi_id == "poi_001"
    assert results[1].poi_id == "poi_002"


# ============================================
# Test Confidence Calculation
# ============================================

@patch('ml.inference.scorer.joblib.load')
def test_confidence_higher_for_complete_poi(mock_load, mock_model,
                                            sample_poi_complete, sample_poi_minimal, tmp_path):
    """Test that confidence is higher for POIs with more complete data."""
    mock_load.return_value = mock_model
    model_path = tmp_path / "test_model.pkl"

    scorer = POIQualityScorer(model_path=model_path)

    result_complete = scorer.score_poi(sample_poi_complete)
    result_minimal = scorer.score_poi(sample_poi_minimal)

    assert result_complete.confidence > result_minimal.confidence


# ============================================
# Test POIScoringResult
# ============================================

def test_scoring_result_to_dict():
    """Test POIScoringResult serialization to dict."""
    result = POIScoringResult(
        poi_id="test_001",
        quality_score=85.5,
        confidence=0.92,
        features={"has_name": 1.0, "has_description": 0.0},
        timestamp="2025-01-15T10:30:00",
        model_version="v1.0.0"
    )

    result_dict = result.to_dict()

    assert result_dict["poi_id"] == "test_001"
    assert result_dict["quality_score"] == 85.5
    assert result_dict["confidence"] == 0.92
    assert "has_name" in result_dict["features"]


# ============================================
# Test Feature Importance
# ============================================

@patch('ml.inference.scorer.joblib.load')
def test_get_feature_importance(mock_load, mock_model, tmp_path):
    """Test feature importance extraction."""
    mock_load.return_value = mock_model
    model_path = tmp_path / "test_model.pkl"

    scorer = POIQualityScorer(model_path=model_path)
    importance = scorer.get_feature_importance(top_n=5)

    assert len(importance) <= 5
    assert all(isinstance(v, (int, float)) for v in importance.values())


# ============================================
# Test Model Info
# ============================================

@patch('ml.inference.scorer.joblib.load')
def test_get_model_info(mock_load, mock_model, tmp_path):
    """Test model info retrieval."""
    mock_load.return_value = mock_model
    model_path = tmp_path / "test_model.pkl"

    scorer = POIQualityScorer(model_path=model_path)
    info = scorer.get_model_info()

    assert "model_type" in info
    assert "model_version" in info
    assert "num_features" in info
    assert info["num_features"] == 17


# ============================================
# Test Edge Cases & Error Handling
# ============================================

def test_extract_features_with_none_values():
    """Test feature extraction handles None values gracefully."""
    scorer = POIQualityScorer.__new__(POIQualityScorer)
    poi_with_nones = {
        "id": "test",
        "name": None,
        "description": None,
        "latitude": None,
        "longitude": None
    }

    features = scorer.extract_features(poi_with_nones)

    assert features["has_name"] == 0.0
    assert features["has_description"] == 0.0
    assert features["has_gps"] == 0.0


def test_extract_features_with_empty_strings():
    """Test feature extraction handles empty strings."""
    scorer = POIQualityScorer.__new__(POIQualityScorer)
    poi_empty = {
        "id": "test",
        "name": "",
        "description": "",
        "latitude": 48.0,
        "longitude": 2.0
    }

    features = scorer.extract_features(poi_empty)

    assert features["has_name"] == 0.0
    assert features["has_description"] == 0.0
    assert features["description_length"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
