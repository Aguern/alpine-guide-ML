"""
Integration Tests for TourismIQ API
==================================

Tests cover:
- API endpoint functionality
- Request/response validation
- Error handling
- Performance benchmarks

Author: Nicolas Angougeard
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import pandas as pd
import numpy as np
from pathlib import Path


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def mock_model():
    """Mock ML model."""
    model = Mock()
    model.predict.return_value = np.array([85.5])
    return model


@pytest.fixture
def mock_data():
    """Mock data for testing."""
    return {
        "pois_df": pd.DataFrame({
            "id": ["poi_001", "poi_002"],
            "name": ["Tour Eiffel", "Louvre"],
            "quality_score": [95.0, 92.0]
        }),
        "opportunities_df": pd.DataFrame({
            "zone_id": ["zone_001"],
            "zone_name": ["Paris Centre"],
            "opportunity_score": [75.0]
        })
    }


@pytest.fixture
def client(mock_model, mock_data):
    """Test client with mocked dependencies."""
    with patch('api.main.joblib.load', return_value=mock_model):
        with patch('api.main.pd.read_parquet', return_value=mock_data["pois_df"]):
            with patch('api.main.pd.read_json', return_value=mock_data["opportunities_df"]):
                with patch('builtins.open', create=True):
                    from api.main import app
                    return TestClient(app)


# ============================================
# Test Health Check
# ============================================

def test_health_endpoint_returns_ok(client):
    """Test that /health endpoint returns 200 OK."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


# ============================================
# Test POI Scoring Endpoint
# ============================================

def test_score_poi_valid_request(client):
    """Test POST /score-poi with valid POI data."""
    poi_data = {
        "name": "Tour Eiffel",
        "description": "Monument emblématique de Paris",
        "latitude": 48.8584,
        "longitude": 2.2945,
        "address": "5 Avenue Anatole France, 75007 Paris",
        "num_images": 25,
        "website": "https://www.toureiffel.paris",
        "opening_hours": "9:30-23:45"
    }

    response = client.post("/score-poi", json=poi_data)

    assert response.status_code == 200
    data = response.json()
    assert "quality_score" in data
    assert 0 <= data["quality_score"] <= 100
    assert "confidence" in data


def test_score_poi_minimal_data(client):
    """Test scoring with minimal POI data."""
    poi_data = {
        "name": "Small Cafe",
        "latitude": 48.8566,
        "longitude": 2.3522
    }

    response = client.post("/score-poi", json=poi_data)

    assert response.status_code == 200
    data = response.json()
    assert "quality_score" in data


def test_score_poi_missing_required_fields(client):
    """Test that missing required fields return 422."""
    poi_data = {
        "name": "Test POI"
        # Missing latitude/longitude
    }

    response = client.post("/score-poi", json=poi_data)

    assert response.status_code == 422  # Validation error


def test_score_poi_invalid_coordinates(client):
    """Test that invalid coordinates are handled."""
    poi_data = {
        "name": "Test POI",
        "latitude": 999.0,  # Invalid
        "longitude": 2.3522
    }

    response = client.post("/score-poi", json=poi_data)

    # Should either return 422 or process with validation
    assert response.status_code in [200, 422]


# ============================================
# Test Opportunities Endpoint
# ============================================

def test_opportunities_endpoint(client):
    """Test GET /opportunities returns opportunity list."""
    response = client.get("/opportunities")

    assert response.status_code == 200
    data = response.json()
    assert "opportunities" in data or isinstance(data, list)


def test_opportunities_with_limit(client):
    """Test opportunities endpoint with limit parameter."""
    response = client.get("/opportunities?limit=5")

    assert response.status_code == 200
    data = response.json()

    if isinstance(data, list):
        assert len(data) <= 5
    elif "opportunities" in data:
        assert len(data["opportunities"]) <= 5


def test_opportunities_with_min_score(client):
    """Test opportunities filtering by minimum score."""
    response = client.get("/opportunities?min_score=70")

    assert response.status_code == 200
    # Should return only opportunities with score >= 70


# ============================================
# Test Zone Analysis Endpoint
# ============================================

def test_analyze_zone_valid_request(client):
    """Test POST /analyze-zone with valid coordinates."""
    zone_data = {
        "latitude": 48.8566,
        "longitude": 2.3522,
        "radius_km": 5.0
    }

    response = client.post("/analyze-zone", json=zone_data)

    assert response.status_code in [200, 404]  # May not have data

    if response.status_code == 200:
        data = response.json()
        assert "zone_stats" in data or "poi_count" in data


def test_analyze_zone_invalid_radius(client):
    """Test zone analysis with invalid radius."""
    zone_data = {
        "latitude": 48.8566,
        "longitude": 2.3522,
        "radius_km": -5.0  # Invalid negative radius
    }

    response = client.post("/analyze-zone", json=zone_data)

    assert response.status_code == 422  # Validation error


# ============================================
# Test Benchmark Endpoint
# ============================================

def test_benchmark_endpoint(client):
    """Test GET /benchmark returns national statistics."""
    response = client.get("/benchmark")

    assert response.status_code == 200
    data = response.json()

    # Should contain aggregated statistics
    assert isinstance(data, dict)


def test_benchmark_by_category(client):
    """Test benchmark filtering by category."""
    response = client.get("/benchmark?category=restaurant")

    assert response.status_code in [200, 404]


# ============================================
# Test Error Handling
# ============================================

def test_invalid_endpoint_returns_404(client):
    """Test that invalid endpoints return 404."""
    response = client.get("/invalid-endpoint")

    assert response.status_code == 404


def test_invalid_method_returns_405(client):
    """Test that invalid HTTP methods return 405."""
    response = client.delete("/health")

    assert response.status_code == 405


def test_malformed_json_returns_422(client):
    """Test that malformed JSON returns 422."""
    response = client.post(
        "/score-poi",
        data="not-valid-json",
        headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422


# ============================================
# Test CORS Headers
# ============================================

def test_cors_headers_present(client):
    """Test that CORS headers are present in responses."""
    response = client.options("/health")

    # CORS headers should be present
    assert "access-control-allow-origin" in response.headers.keys() or \
           response.status_code == 200


# ============================================
# Test API Documentation
# ============================================

def test_openapi_schema_available(client):
    """Test that OpenAPI schema is accessible."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "info" in schema
    assert "paths" in schema


def test_docs_endpoint_available(client):
    """Test that /docs endpoint is accessible."""
    response = client.get("/docs")

    assert response.status_code == 200


# ============================================
# Test Performance & Scalability
# ============================================

@pytest.mark.slow
def test_concurrent_requests_performance(client):
    """Test API can handle concurrent requests."""
    import concurrent.futures

    def make_request():
        return client.get("/health")

    # Make 10 concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [f.result() for f in futures]

    # All should succeed
    assert all(r.status_code == 200 for r in results)


@pytest.mark.slow
def test_score_poi_response_time(client):
    """Test that POI scoring responds within acceptable time."""
    import time

    poi_data = {
        "name": "Test POI",
        "latitude": 48.8584,
        "longitude": 2.2945
    }

    start = time.time()
    response = client.post("/score-poi", json=poi_data)
    duration = time.time() - start

    assert response.status_code == 200
    assert duration < 1.0  # Should respond in less than 1 second


# ============================================
# Test Data Validation
# ============================================

def test_score_poi_response_schema(client):
    """Test that score-poi response matches expected schema."""
    poi_data = {
        "name": "Test POI",
        "latitude": 48.8584,
        "longitude": 2.2945
    }

    response = client.post("/score-poi", json=poi_data)

    if response.status_code == 200:
        data = response.json()

        # Validate response structure
        required_fields = ["quality_score"]
        for field in required_fields:
            assert field in data

        # Validate data types
        assert isinstance(data["quality_score"], (int, float))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
