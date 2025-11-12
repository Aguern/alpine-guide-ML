# Contributing to TourismIQ Platform

Thank you for considering contributing to TourismIQ Platform! This document provides guidelines for contributing to the project.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Workflow](#development-workflow)
4. [Code Standards](#code-standards)
5. [Testing Guidelines](#testing-guidelines)
6. [Pull Request Process](#pull-request-process)

---

## Code of Conduct

This project adheres to professional standards of collaboration:

- Be respectful and constructive
- Focus on technical merit
- Welcome diverse perspectives
- Provide actionable feedback

---

## Getting Started

### 1. Fork and Clone

```bash
git clone https://github.com/yourusername/tourismiq-platform.git
cd tourismiq-platform
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
make install-dev

# Copy environment file
cp .env.example .env
# Edit .env with your configuration
```

### 3. Verify Setup

```bash
# Run tests
make test

# Start services
make docker-up
```

---

## Development Workflow

### Branch Naming

```
feature/add-new-model       # New features
bugfix/fix-cache-issue      # Bug fixes
docs/update-readme          # Documentation
refactor/improve-api        # Code refactoring
```

### Commit Messages

Follow the Conventional Commits specification:

```
feat: add hyperparameter tuning with Optuna
fix: resolve cache invalidation bug
docs: update ML pipeline documentation
test: add integration tests for /score-poi endpoint
refactor: extract feature engineering into separate module
```

**Format:**
```
<type>: <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

---

## Code Standards

### Python Style Guide

We follow PEP 8 with some modifications:

```python
# Maximum line length: 100 characters (not 79)
# Use Black for formatting
# Use type hints everywhere
# Write docstrings for all public functions
```

### Type Hints

All functions must have type hints:

```python
def score_poi(poi_data: Dict[str, Any]) -> POIScoringResult:
    """
    Score a POI's quality.

    Args:
        poi_data: Dictionary containing POI information

    Returns:
        POIScoringResult with quality score and metadata
    """
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def train_model(X: pd.DataFrame, y: pd.Series) -> GradientBoostingRegressor:
    """
    Train a Gradient Boosting model.

    Args:
        X: Feature matrix (n_samples, n_features)
        y: Target vector (n_samples,)

    Returns:
        Trained GradientBoostingRegressor model

    Raises:
        ValueError: If X and y have different lengths
    """
    if len(X) != len(y):
        raise ValueError("X and y must have the same length")

    model = GradientBoostingRegressor()
    model.fit(X, y)
    return model
```

### Code Formatting

```bash
# Format code with Black
make format

# Check formatting without changing files
black --check ml/ api/ data/
```

### Linting

```bash
# Run all linters
make lint

# Individual tools
flake8 ml/ api/
mypy ml/ api/
```

---

## Testing Guidelines

### Test Coverage Requirements

- **Minimum coverage:** 80%
- **New features:** Must include tests
- **Bug fixes:** Must include regression tests

### Writing Tests

#### Unit Tests

```python
# tests/unit/test_scorer.py

def test_extract_features_handles_missing_data():
    """Test that feature extraction handles None values gracefully."""
    scorer = POIQualityScorer()
    poi_data = {"name": None, "latitude": 48.0}

    features = scorer.extract_features(poi_data)

    assert features["has_name"] == 0.0
    assert features["latitude"] == 48.0
```

#### Integration Tests

```python
# tests/integration/test_api.py

def test_score_poi_endpoint(client):
    """Test /score-poi endpoint with valid data."""
    response = client.post("/score-poi", json={
        "name": "Test POI",
        "latitude": 48.8584,
        "longitude": 2.2945
    })

    assert response.status_code == 200
    data = response.json()
    assert "quality_score" in data
```

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
pytest tests/unit/test_scorer.py -v

# Run tests matching pattern
pytest -k "test_score" -v
```

---

## Pull Request Process

### 1. Before Submitting

Checklist:

- [ ] Code follows style guidelines
- [ ] All tests pass: `make test`
- [ ] Code is formatted: `make format`
- [ ] Linters pass: `make lint`
- [ ] Documentation is updated
- [ ] Commit messages follow conventions

### 2. PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Performance Impact
- [ ] No performance impact
- [ ] Performance improved
- [ ] Performance regression (explain)

## Documentation
- [ ] README updated
- [ ] Docstrings updated
- [ ] Architecture docs updated

## Checklist
- [ ] Tests pass locally
- [ ] Code is formatted (Black)
- [ ] Linters pass (flake8, mypy)
- [ ] No breaking changes (or documented)
```

### 3. Review Process

1. **Automated Checks:** CI/CD pipeline runs tests and linters
2. **Code Review:** At least one maintainer reviews
3. **Approval:** PR must be approved before merge
4. **Merge:** Squash and merge to main branch

---

## Project Structure Guidelines

### Adding New Features

#### New ML Model

```
ml/models/
├── new_model/
│   ├── __init__.py
│   ├── model.pkl
│   ├── metrics.json
│   └── features.txt
```

#### New API Endpoint

```python
# api/endpoints/new_endpoint.py

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class NewRequest(BaseModel):
    field: str

@router.post("/new-endpoint")
async def new_endpoint(request: NewRequest):
    """Endpoint docstring."""
    ...
```

#### New Data Collector

```python
# data/collectors/new_collector.py

from typing import List, Dict

class NewCollector:
    """Docstring."""

    def collect(self) -> List[Dict]:
        """Collect data from source."""
        ...

    def validate(self, data: List[Dict]) -> bool:
        """Validate collected data."""
        ...
```

---

## Questions?

- **Issues:** Open a GitHub issue
- **Email:** contact@example.com
- **Discussions:** Use GitHub Discussions

---

Thank you for contributing to TourismIQ Platform! 🚀
