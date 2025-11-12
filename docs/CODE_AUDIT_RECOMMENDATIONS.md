# Code Audit & Recommendations

**Date:** November 12, 2025
**Auditor:** Claude (AI Assistant)
**Scope:** Code quality, testing strategy, MLOps best practices

---

## Executive Summary

The **Alpine Guide ML** project demonstrates strong engineering fundamentals with clean architecture, comprehensive testing, and production-ready code. However, several improvements can elevate it to senior-level standards expected in top-tier ML engineering teams.

**Overall Assessment:** 8.5/10

**Key Strengths:**
- Type-safe code with Pydantic and type hints
- Comprehensive docstrings in inference module
- Good separation of concerns
- Docker-ready infrastructure
- 45+ tests covering core functionality

**Critical Improvements Needed:**
1. **Data versioning:** Large files (features_ml.parquet, scorer.pkl) were tracked in Git → Fixed
2. **Missing tests:** No tests for feature engineering or data collectors
3. **Hardcoded paths:** Training scripts use relative paths (fragile)
4. **Logging:** Inconsistent use of print() vs logging module

---

## 1. Code Quality Audit

### 1.1 ml/training/03_train_quality_scorer.py

**Score:** 7/10

**Strengths:**
- Well-structured with clear sections
- Comprehensive metrics reporting
- Saves all artifacts (model, metrics, features)

**Issues & Recommendations:**

#### Issue 1: Hardcoded Relative Paths (Critical)

**Current (Line 32-33):**
```python
data_file = Path("../data/processed/features_ml.parquet")
models_dir = Path("../models/quality_scorer")
```

**Problem:** Breaks when script is run from different directories.

**Fix:**
```python
from pathlib import Path

# Get absolute paths relative to project root
BASE_DIR = Path(__file__).parent.parent.parent  # alpine-guide-ML/
DATA_DIR = BASE_DIR / "data" / "processed"
MODELS_DIR = BASE_DIR / "ml" / "models" / "quality_scorer"

data_file = DATA_DIR / "features_ml.parquet"

# Validate paths exist
if not data_file.exists():
    raise FileNotFoundError(
        f"Features file not found: {data_file}\n"
        "Run feature engineering script first: "
        "python ml/training/02_feature_engineering.py"
    )
```

**Impact:** High - Script currently fails if not run from specific directory.

#### Issue 2: Inconsistent Logging (Medium)

**Current:** Mix of print() statements and no structured logging.

**Fix:**
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/training.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Replace prints with:
logger.info(f"Loaded {len(df):,} POIs")
logger.warning("Missing values detected in features")
logger.error("Training failed: {error}", exc_info=True)
```

**Impact:** Medium - Improves observability and debugging.

#### Issue 3: No Hyperparameter Configuration (Low)

**Current:** Hyperparameters hardcoded in script (line 87-96).

**Fix:** Extract to config file.

```python
# config/model_config.yaml
gradient_boosting:
  n_estimators: 200
  learning_rate: 0.1
  max_depth: 5
  min_samples_split: 20
  min_samples_leaf: 15
  subsample: 0.8
  random_state: 42

# Load in script
import yaml

with open(BASE_DIR / "config" / "model_config.yaml") as f:
    config = yaml.safe_load(f)

params = config["gradient_boosting"]
model = GradientBoostingRegressor(**params)
```

**Impact:** Low - Easier hyperparameter tuning, but not critical for current project.

---

### 1.2 ml/inference/scorer.py

**Score:** 9/10

**Strengths:**
- Excellent type hints and docstrings
- Clean dataclass for results
- Proper error handling
- Well-designed API

**Issues & Recommendations:**

#### Issue 1: Feature Validation Missing (Medium)

**Current (Line 172-237):** No validation that all 17 features are extracted.

**Fix:**
```python
def extract_features(self, poi_data: Dict[str, Any]) -> Dict[str, float]:
    """Extract ML features from raw POI data."""
    features = {}

    # ... existing extraction logic ...

    # Validate all required features are present
    missing = set(self.REQUIRED_FEATURES) - set(features.keys())
    if missing:
        raise ValueError(
            f"Feature extraction incomplete. Missing features: {missing}. "
            f"This indicates a bug in the extraction logic."
        )

    # Validate feature types
    for feat_name, feat_value in features.items():
        if not isinstance(feat_value, (int, float)):
            raise TypeError(
                f"Feature '{feat_name}' must be numeric, got {type(feat_value)}"
            )

    return features
```

**Impact:** Medium - Prevents silent failures from feature extraction bugs.

#### Issue 2: Simplistic Confidence Calculation (Low)

**Current (Line 265-271):** Confidence based only on completeness.

**Improved:**
```python
def _calculate_confidence(
    self,
    features: Dict[str, float],
    score: float,
    feature_vector: np.ndarray
) -> float:
    """
    Calculate prediction confidence using multiple signals:
    1. Data completeness
    2. Score extremity (extreme scores often less reliable)
    3. Feature distribution (penalize out-of-distribution inputs)
    """
    # Completeness-based confidence
    completeness_features = [
        "has_name", "has_description", "has_gps",
        "has_address", "has_images"
    ]
    completeness = sum(features[f] for f in completeness_features) / len(completeness_features)
    confidence = 0.5 + completeness * 0.4  # Base: 0.5-0.9

    # Penalize extreme scores (often edge cases)
    if score < 20 or score > 90:
        confidence *= 0.9

    # Optional: Check if features are within training distribution
    # (requires storing feature statistics during training)
    # if hasattr(self, 'feature_stats'):
    #     out_of_bounds = self._check_feature_bounds(features)
    #     confidence *= (1 - 0.1 * out_of_bounds)

    return min(0.95, max(0.5, confidence))
```

**Impact:** Low - Minor improvement in confidence calibration.

---

### 1.3 data/ingestion/openmeteo_collector.py

**Score:** 8.5/10

**Strengths:**
- Clean class structure
- Proper logging
- Good error handling
- Well-documented

**Issues & Recommendations:**

#### Issue 1: No Retry Mechanism (Medium)

**Current (Line 90-104):** Single request attempt, no retries on network errors.

**Fix: Add Exponential Backoff Retries**

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests

class OpenMeteoCollector:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError
        )),
        reraise=True
    )
    def _make_request(
        self,
        lat: float,
        lon: float,
        start_date: str,
        end_date: str
    ) -> Optional[Dict]:
        """
        Make API request with automatic retries.

        Retries 3 times with exponential backoff (2s, 4s, 8s)
        on network errors. Raises exception after final failure.
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,sunshine_duration",
            "timezone": "Europe/Paris"
        }

        try:
            self.stats["api_calls"] += 1
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()  # Raise HTTPError for bad responses
            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [429, 503]:  # Rate limit or service unavailable
                logger.warning(f"API rate limited or unavailable: {e}")
                raise  # Trigger retry
            else:
                logger.error(f"HTTP error {e.response.status_code}: {e}")
                self.stats["errors"] += 1
                return None

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.warning(f"Network error, will retry: {e}")
            self.stats["errors"] += 1
            raise  # Trigger retry

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            self.stats["errors"] += 1
            return None
```

**Impact:** Medium - Improves reliability when external APIs are flaky.

#### Issue 2: No Rate Limiting (Low)

**Current:** Requests fire as fast as possible, risk of hitting API limits.

**Fix:**
```python
import time

class OpenMeteoCollector:
    def __init__(self, rate_limit_seconds: float = 0.5):
        """
        Args:
            rate_limit_seconds: Minimum seconds between API calls
        """
        self.rate_limit = rate_limit_seconds
        self.last_request_time = 0.0
        self.climate_data = []
        self.stats = {
            "regions_collected": 0,
            "api_calls": 0,
            "errors": 0
        }

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            sleep_time = self.rate_limit - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _make_request(self, ...):
        self._rate_limit()  # Enforce before each request
        # ... rest of request logic
```

**Impact:** Low - Nice to have, but Open-Meteo is very generous with free tier.

---

## 2. Testing Strategy Audit

### Current State

**Total Tests:** 45+
- **Unit Tests:** 20+ (ml/inference/scorer.py)
- **Integration Tests:** 25+ (API endpoints)

**Coverage:** Good for inference and API layers, but **gaps in data pipeline**.

### Missing Tests (Critical)

#### 2.1 Feature Engineering Tests

**File:** `tests/unit/test_feature_engineering.py` (NEW)

**Why Critical:** Feature bugs silently corrupt model input → bad predictions.

**Recommended Tests:**

```python
"""
Unit Tests for Feature Engineering
==================================

Tests the ml/training/02_feature_engineering.py module.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Import the feature engineering functions (assuming they're extracted to a module)
from ml.training.feature_engineering import (
    calculate_poi_density,
    enrich_with_insee_data,
    calculate_freshness_features,
    extract_completeness_features
)


class TestPOIDensityCalculation:
    """Test geographic POI density calculation."""

    def test_density_within_radius(self):
        """Test that density counts POIs within 10km radius."""
        target_poi = {"latitude": 45.75, "longitude": 4.85}
        nearby_pois = pd.DataFrame({
            "latitude": [45.76, 45.80, 45.90],  # ~1km, ~5km, ~15km
            "longitude": [4.86, 4.90, 5.10]
        })

        density = calculate_poi_density(target_poi, nearby_pois, radius_km=10)

        assert density == 2  # Only first two within 10km

    def test_density_handles_empty_dataset(self):
        """Test that density is 0 for empty POI dataset."""
        target_poi = {"latitude": 45.75, "longitude": 4.85}
        empty_pois = pd.DataFrame({"latitude": [], "longitude": []})

        density = calculate_poi_density(target_poi, empty_pois, radius_km=10)

        assert density == 0

    def test_density_excludes_self(self):
        """Test that target POI doesn't count itself."""
        target_poi = {"uuid": "poi_001", "latitude": 45.75, "longitude": 4.85}
        pois_including_self = pd.DataFrame({
            "uuid": ["poi_001", "poi_002"],
            "latitude": [45.75, 45.76],  # Exact location + nearby
            "longitude": [4.85, 4.86]
        })

        density = calculate_poi_density(
            target_poi,
            pois_including_self,
            radius_km=10,
            exclude_self=True
        )

        assert density == 1  # Should exclude poi_001


class TestINSEEEnrichment:
    """Test INSEE socio-economic data enrichment."""

    @pytest.fixture
    def insee_data(self):
        """Sample INSEE commune data."""
        return pd.DataFrame({
            "insee_code": ["69123", "38185"],
            "commune_name": ["Lyon", "Grenoble"],
            "latitude": [45.75, 45.18],
            "longitude": [4.85, 5.72],
            "median_salary": [2800.0, 2500.0],
            "population": [516000, 158000]
        })

    def test_enrich_matches_nearest_commune(self, insee_data):
        """Test that enrichment finds nearest commune by GPS."""
        poi = {"latitude": 45.76, "longitude": 4.86}  # Near Lyon

        enriched = enrich_with_insee_data(poi, insee_data)

        assert enriched["insee_salary_median"] == 2800.0
        assert enriched["population"] == 516000
        assert enriched["matched_commune"] == "Lyon"

    def test_enrich_handles_missing_data(self, insee_data):
        """Test graceful handling when no INSEE data available."""
        poi = {"latitude": 90.0, "longitude": 0.0}  # North Pole

        enriched = enrich_with_insee_data(poi, insee_data, default_salary=2000)

        assert enriched["insee_salary_median"] == 2000.0  # Default
        assert enriched["population"] == 10000  # Default
        assert "matched_commune" not in enriched or enriched["matched_commune"] is None


class TestFreshnessFeatures:
    """Test temporal freshness calculation."""

    def test_recent_poi_flagged_correctly(self):
        """Test that POI updated <6 months ago is marked recent."""
        poi = {
            "updated_at": (datetime.now() - timedelta(days=90)).isoformat()
        }

        features = calculate_freshness_features(poi)

        assert features["days_since_update"] < 100
        assert features["is_recent"] == 1.0

    def test_old_poi_flagged_correctly(self):
        """Test that POI updated >6 months ago is not recent."""
        poi = {
            "updated_at": (datetime.now() - timedelta(days=365)).isoformat()
        }

        features = calculate_freshness_features(poi)

        assert features["days_since_update"] > 300
        assert features["is_recent"] == 0.0

    def test_missing_updated_at_defaults_to_old(self):
        """Test that missing updated_at is treated as old data."""
        poi = {}  # No updated_at field

        features = calculate_freshness_features(poi)

        assert features["days_since_update"] == 365.0  # Default
        assert features["is_recent"] == 0.0

    def test_invalid_date_format_handled(self):
        """Test graceful handling of malformed dates."""
        poi = {"updated_at": "not-a-valid-date"}

        features = calculate_freshness_features(poi)

        # Should not crash, should return defaults
        assert "days_since_update" in features
        assert features["is_recent"] in [0.0, 1.0]


class TestCompletenessFeatures:
    """Test completeness binary features."""

    def test_complete_poi_has_all_flags(self):
        """Test that fully complete POI gets all 1.0 flags."""
        poi = {
            "name": "Tour Eiffel",
            "description": "Famous monument",
            "latitude": 48.8584,
            "longitude": 2.2945,
            "address": "5 Avenue Anatole France",
            "images": ["img1.jpg", "img2.jpg"],
            "opening_hours": "9:00-23:00",
            "phone": "+33123456789",
            "email": "contact@example.com"
        }

        features = extract_completeness_features(poi)

        assert features["has_name"] == 1.0
        assert features["has_description"] == 1.0
        assert features["has_gps"] == 1.0
        assert features["has_address"] == 1.0
        assert features["has_images"] == 1.0
        assert features["has_opening_hours"] == 1.0
        assert features["has_contact"] == 1.0

    def test_minimal_poi_has_expected_flags(self):
        """Test POI with only name and GPS."""
        poi = {
            "name": "Small Cafe",
            "latitude": 45.75,
            "longitude": 4.85
        }

        features = extract_completeness_features(poi)

        assert features["has_name"] == 1.0
        assert features["has_description"] == 0.0
        assert features["has_gps"] == 1.0
        assert features["has_address"] == 0.0
        assert features["has_images"] == 0.0
        assert features["has_opening_hours"] == 0.0
        assert features["has_contact"] == 0.0

    def test_empty_strings_treated_as_missing(self):
        """Test that empty strings don't count as present."""
        poi = {
            "name": "",
            "description": "   ",  # Whitespace only
            "latitude": 45.75,
            "longitude": 4.85
        }

        features = extract_completeness_features(poi)

        assert features["has_name"] == 0.0
        assert features["has_description"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Impact:** High - Prevents silent feature bugs that degrade model performance.

---

#### 2.2 Data Collector Tests (with Mocking)

**File:** `tests/unit/test_collectors.py` (NEW)

**Why Important:** Data collectors hit external APIs → need mocking for fast, reliable tests.

**Recommended Tests:**

```python
"""
Unit Tests for Data Collectors
==============================

Tests data collection modules with mocked API responses.
"""

import pytest
from unittest.mock import Mock, patch
import requests
import pandas as pd

from data.ingestion.openmeteo_collector import OpenMeteoCollector
from data.ingestion.water_temperature import WaterTemperatureCollector


class TestOpenMeteoCollector:
    """Test Open-Meteo API collector."""

    @patch('requests.get')
    def test_successful_request(self, mock_get):
        """Test that collector parses API response correctly."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "daily": {
                "temperature_2m_max": [15.0, 16.0, 14.5],
                "temperature_2m_min": [8.0, 9.0, 7.5],
                "precipitation_sum": [0.0, 2.5, 1.0],
                "sunshine_duration": [28800, 25200, 21600]  # seconds
            }
        }
        mock_get.return_value = mock_response

        collector = OpenMeteoCollector()
        data = collector._make_request(45.75, 4.85, "2024-01-01", "2024-01-03")

        assert data is not None
        assert "daily" in data
        assert len(data["daily"]["temperature_2m_max"]) == 3
        assert collector.stats["api_calls"] == 1
        assert collector.stats["errors"] == 0

    @patch('requests.get')
    def test_handles_http_errors(self, mock_get):
        """Test graceful handling of HTTP errors."""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_get.return_value = mock_response

        collector = OpenMeteoCollector()
        data = collector._make_request(45.75, 4.85, "2024-01-01", "2024-01-03")

        assert data is None
        assert collector.stats["errors"] == 1

    @patch('requests.get')
    def test_handles_network_errors(self, mock_get):
        """Test handling of network failures."""
        # Mock network timeout
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

        collector = OpenMeteoCollector()
        data = collector._make_request(45.75, 4.85, "2024-01-01", "2024-01-03")

        assert data is None
        assert collector.stats["errors"] == 1

    @patch('requests.get')
    def test_climate_classification(self, mock_get):
        """Test climate type classification logic."""
        # Mock response for Mediterranean climate
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "daily": {
                "temperature_2m_max": [20.0] * 365,
                "temperature_2m_min": [10.0] * 365,
                "precipitation_sum": [1.0] * 365,  # 365mm total
                "sunshine_duration": [36000] * 365
            }
        }
        mock_get.return_value = mock_response

        collector = OpenMeteoCollector()
        collector.collect_regional_climate(year=2024)

        # Check that at least one Mediterranean region was identified
        climate_types = [d["climate_type"] for d in collector.climate_data]
        assert "mediterranean" in climate_types or "oceanic" in climate_types


class TestWaterTemperatureCollector:
    """Test Hub'Eau water temperature collector."""

    @patch('requests.get')
    def test_successful_collection(self, mock_get):
        """Test successful water temperature data collection."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "code_site": "06015000",
                    "temperature": 18.5,
                    "date_mesure": "2024-07-15"
                }
            ]
        }
        mock_get.return_value = mock_response

        collector = WaterTemperatureCollector()
        data = collector.collect_site("06015000")

        assert data is not None
        assert "temperature" in data
        assert data["temperature"] == 18.5

    @patch('requests.get')
    def test_missing_site_returns_none(self, mock_get):
        """Test that invalid site code returns None."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        collector = WaterTemperatureCollector()
        data = collector.collect_site("invalid_site_code")

        assert data is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Impact:** Medium - Ensures data pipeline robustness without depending on external APIs.

---

## 3. MLOps Best Practices

### 3.1 Data Versioning (Fixed)

**Issue:** Large files tracked in Git:
- `data/processed/features_ml.parquet` (4.2MB)
- Potential model files (`scorer.pkl`)

**Fix Applied:**

Updated `.gitignore`:
```gitignore
# Processed data (too large, regenerate with scripts)
data/processed/*.parquet
data/processed/*.csv
!data/processed/.gitkeep

# ML models (too large, regenerate with training scripts)
ml/models/**/*.pkl
ml/models/**/*.joblib
!ml/models/**/.gitkeep
# Keep model metadata (lightweight)
!ml/models/**/metrics.json
!ml/models/**/features.txt
```

Created `.gitkeep` files with regeneration instructions:
- `data/processed/.gitkeep`
- `ml/models/.gitkeep`

**Recommended Next Step: Use DVC (Data Version Control)**

```bash
# Install DVC
pip install dvc dvc-gdrive

# Initialize DVC
dvc init

# Track large files with DVC
dvc add data/processed/features_ml.parquet
dvc add ml/models/quality_scorer/scorer.pkl

# Configure remote storage (example: Google Drive)
dvc remote add -d storage gdrive://your-folder-id

# Push data to remote
dvc push

# Commit DVC metadata (small .dvc files)
git add data/processed/features_ml.parquet.dvc ml/models/.gitignore
git commit -m "Track datasets and models with DVC"
```

**Benefits:**
- Version datasets and models like code
- Share large files without bloating Git repo
- Reproduce any training run

---

### 3.2 Environment Configuration

**Current State:** `.env.example` is comprehensive and well-documented.

**Score:** 9/10

**Minor Improvement:**

Add section for model versioning:

```bash
# ============================================
# Model Versioning (Optional - DVC)
# ============================================
DVC_REMOTE_STORAGE=gdrive://folder-id
MODEL_VERSION=v1.0.0
ENABLE_MODEL_AUTO_UPDATE=false
```

---

### 3.3 Experiment Tracking (Future Enhancement)

**Recommendation:** Add MLflow or Weights & Biases for experiment tracking.

**Example with MLflow:**

```python
# ml/training/03_train_quality_scorer.py

import mlflow
import mlflow.sklearn

# Start MLflow run
mlflow.set_experiment("poi-quality-scorer")

with mlflow.start_run():
    # Log hyperparameters
    mlflow.log_params(params)

    # Train model
    model = GradientBoostingRegressor(**params)
    model.fit(X_train, y_train)

    # Log metrics
    mlflow.log_metrics({
        "train_r2": train_r2,
        "test_r2": test_r2,
        "test_mae": test_mae,
        "test_rmse": test_rmse
    })

    # Log model
    mlflow.sklearn.log_model(model, "quality_scorer")

    # Log feature importance plot
    import matplotlib.pyplot as plt
    fig = plot_feature_importance(feature_importance)
    mlflow.log_figure(fig, "feature_importance.png")
```

**Benefits:**
- Track all experiments in one place
- Compare models easily
- Reproduce any training run
- Share results with team

---

## 4. Priority Action Items

### High Priority (Do First)

1. **Fix hardcoded paths in training scripts** (2 hours)
   - Impact: Prevents script failures
   - Files: `ml/training/*.py`

2. **Add feature engineering tests** (4 hours)
   - Impact: Catches feature bugs early
   - File: `tests/unit/test_feature_engineering.py`

3. **Add retry logic to data collectors** (2 hours)
   - Impact: Improves reliability
   - Files: `data/ingestion/*_collector.py`

### Medium Priority (Next Sprint)

4. **Add structured logging** (3 hours)
   - Impact: Better observability
   - Files: All modules

5. **Add data collector tests with mocking** (3 hours)
   - Impact: Test data pipeline
   - File: `tests/unit/test_collectors.py`

6. **Extract hyperparameters to config** (1 hour)
   - Impact: Easier tuning
   - File: `config/model_config.yaml`

### Low Priority (Nice to Have)

7. **Implement DVC for data versioning** (4 hours)
   - Impact: Professional data management
   - Setup: `dvc init`, configure remote

8. **Add MLflow experiment tracking** (4 hours)
   - Impact: Track experiments
   - Integration: `mlflow.log_*` calls

9. **Improve confidence calculation** (2 hours)
   - Impact: Better uncertainty estimates
   - File: `ml/inference/scorer.py`

---

## 5. Conclusion

The **Alpine Guide ML** project is already at a high standard for a portfolio project. The recommended improvements will elevate it to senior-level quality expected at top ML companies.

**Estimated Total Effort:** 25-30 hours to implement all high and medium priority items.

**ROI for Recruiting:**
- **High priority fixes** → Demonstrate attention to production robustness
- **Testing improvements** → Show software engineering rigor
- **MLOps best practices** → Prove readiness for professional ML teams

**Final Grade After Improvements:** 9.5/10

---

**Document Version:** 1.0
**Date:** November 12, 2025
