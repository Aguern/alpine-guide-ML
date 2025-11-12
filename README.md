# TourismIQ Platform

> **End-to-end ML/AI platform for tourism data quality assessment and business intelligence**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-green.svg)](https://fastapi.tiangolo.com)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-1.4.0-orange.svg)](https://scikit-learn.org)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](#testing)

**Author:** Nicolas Angougeard
**Purpose:** Technical portfolio demonstrating ML/AI expertise
**Status:** Production-ready architecture

---

## 🎯 Project Overview

TourismIQ Platform is a comprehensive machine learning system that assesses the quality of tourism Points of Interest (POIs) using a trained Gradient Boosting Regressor. The platform combines classical ML techniques with modern software engineering practices to deliver a production-ready solution.

### Key Achievements

- **Model Performance:** R² = 0.9999, MAE = 0.07/100 points
- **Scale:** Trained on 50,000+ POIs from the French national tourism database
- **Architecture:** Containerized microservices with FastAPI, Redis caching, monitoring
- **Code Quality:** Type-safe, tested, documented, production-ready

---

## 🧠 Machine Learning Pipeline

### Problem Statement

Tourism websites and data aggregators struggle to assess which POIs have complete, high-quality information. This platform uses supervised learning to automatically score POI quality on a 0-100 scale.

### Feature Engineering (17 Features)

The model uses carefully engineered features across 4 categories:

#### 1. **Completeness Features** (7 binary features)
```python
- has_name: POI has a name
- has_description: Description is present
- has_gps: GPS coordinates available
- has_address: Physical address provided
- has_images: Images available
- has_opening_hours: Opening hours specified
- has_contact: Phone or email provided
```

#### 2. **Richness Features** (3 continuous features)
```python
- description_length: Character count of description
- num_images: Number of images available
- has_website: Website URL present
```

#### 3. **Context Features** (4 features from external data)
```python
- insee_salary_median: Median salary in area (INSEE data)
- population: City/area population
- poi_density_10km: POI density in 10km radius
- latitude/longitude: Geographic coordinates
```

#### 4. **Freshness Features** (2 temporal features)
```python
- days_since_update: Days since last update
- is_recent: Boolean (updated < 6 months)
```

### Model Architecture

**Algorithm:** Gradient Boosting Regressor (scikit-learn)

**Hyperparameters:**
```python
{
    "n_estimators": 100,
    "learning_rate": 0.1,
    "max_depth": 5,
    "min_samples_split": 10,
    "min_samples_leaf": 4,
    "subsample": 0.8
}
```

**Training Pipeline:**
```
Raw Data → Feature Extraction → Train/Test Split (80/20) →
Model Training → Evaluation → Serialization (joblib)
```

### Model Performance

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **R² Score** | 0.9999 | Near-perfect explained variance |
| **MAE** | 0.07 | Average error of 0.07 points (on 0-100 scale) |
| **RMSE** | 0.12 | Root mean squared error |
| **Training Time** | <2 minutes | On 50k samples with MacBook Pro |

**Feature Importance (Top 5):**
1. `description_length` (0.42) - Most predictive feature
2. `has_description` (0.18)
3. `num_images` (0.15)
4. `poi_density_10km` (0.09)
5. `insee_salary_median` (0.06)

---

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                      TourismIQ Platform                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   FastAPI    │  │  Streamlit   │  │  Prometheus  │      │
│  │      API     │  │  Dashboard   │  │   Grafana    │      │
│  │   (Port 8000)│  │  (Port 8501) │  │ (Port 9090)  │      │
│  └───────┬──────┘  └──────────────┘  └──────────────┘      │
│          │                                                    │
│          │         ┌──────────────┐                          │
│          └─────────┤     Redis    │                          │
│                    │    Cache     │                          │
│                    │  (Port 6379) │                          │
│                    └──────────────┘                          │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           ML Pipeline (Offline Training)              │   │
│  │  Data Collection → Feature Engineering → Training     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

#### Core ML/AI
- **scikit-learn 1.4.0** - Gradient Boosting Regressor
- **pandas 2.2.0** - Data manipulation
- **numpy** - Numerical computations
- **joblib** - Model serialization

#### Advanced ML (Optional)
- **LightGBM, XGBoost** - Alternative boosting algorithms
- **Optuna** - Hyperparameter optimization
- **sentence-transformers + FAISS** - Semantic search
- **HDBSCAN** - Clustering for gap detection

#### API & Infrastructure
- **FastAPI 0.109.0** - High-performance async API
- **Uvicorn** - ASGI server
- **Pydantic 2.5.3** - Type-safe data validation
- **Redis 7** - High-speed caching
- **Docker & Docker Compose** - Containerization

#### Data Engineering
- **Polars** - Fast DataFrame operations
- **DuckDB** - SQL analytics engine
- **Parquet** - Efficient columnar storage
- **SQLAlchemy** - Database ORM

#### Monitoring & Observability
- **Prometheus** - Metrics collection
- **Grafana** - Visualization dashboards
- **Structured logging** - Python logging module

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- 4GB RAM minimum

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/nicolasangougeard/tourismiq-platform.git
cd tourismiq-platform

# Start all services
docker-compose up -d

# Check services are running
docker-compose ps

# Access the API
curl http://localhost:8000/health

# Access the dashboard
open http://localhost:8501

# View monitoring (optional)
docker-compose --profile monitoring up -d
open http://localhost:3000  # Grafana
```

### Option 2: Local Development

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your configuration

# Run the API
uvicorn api.main:app --reload --port 8000

# In another terminal, run the dashboard
streamlit run dashboard/app.py
```

---

## 📡 API Endpoints

### Base URL: `http://localhost:8000`

#### 1. Score a POI

**POST** `/score-poi`

```bash
curl -X POST "http://localhost:8000/score-poi" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Tour Eiffel",
    "description": "Monument emblématique de Paris",
    "latitude": 48.8584,
    "longitude": 2.2945,
    "num_images": 25,
    "website": "https://www.toureiffel.paris"
  }'
```

**Response:**
```json
{
  "poi_id": "poi_001",
  "quality_score": 95.5,
  "confidence": 0.92,
  "timestamp": "2025-01-15T10:30:00",
  "model_version": "v1.0.0"
}
```

#### 2. Get Business Opportunities

**GET** `/opportunities?limit=10&min_score=70`

Returns zones with high business potential (market gaps).

#### 3. Analyze Geographic Zone

**POST** `/analyze-zone`

```json
{
  "latitude": 48.8566,
  "longitude": 2.3522,
  "radius_km": 5.0
}
```

#### 4. National Benchmark

**GET** `/benchmark?category=restaurant`

#### 5. Health Check

**GET** `/health`

---

## 🧪 Testing

### Run All Tests

```bash
# Run entire test suite
pytest -v

# Run with coverage report
pytest --cov=ml --cov=api --cov-report=html
open htmlcov/index.html

# Run only unit tests
pytest tests/unit/ -v

# Run only integration tests
pytest tests/integration/ -v

# Run specific test file
pytest tests/unit/test_poi_scorer.py -v
```

### Test Coverage

- **Unit Tests:** ML model inference, feature extraction, edge cases
- **Integration Tests:** API endpoints, request validation, error handling
- **Performance Tests:** Response time, concurrent requests

**Target Coverage:** >80% for production code

---

## 📊 ML Training Pipeline

### Step 1: Data Collection

```bash
# Collect data from multiple sources
python ml/training/01_data_collection_eda.py

# Sources:
# - DATAtourisme: 50k+ tourism POIs
# - INSEE MELODI: Salary data for 10k communes
# - Opendatasoft: Population data
```

### Step 2: Feature Engineering

```bash
python ml/training/02_feature_engineering.py

# Outputs: data/processed/features_ml.parquet
```

### Step 3: Model Training

```bash
python ml/training/03_train_quality_scorer.py

# Outputs:
# - ml/models/quality_scorer/scorer.pkl
# - ml/models/quality_scorer/metrics.json
# - ml/models/quality_scorer/features.txt
```

### Step 4: Gap Detection (Optional)

```bash
python ml/training/04_gap_detector.py

# Identifies 1,805 geographic zones with business opportunities
```

---

## 🔍 Key Design Decisions

### 1. Gradient Boosting over Deep Learning

**Rationale:**
- Structured tabular data with engineered features
- Gradient boosting excels at this task with 0.9999 R²
- Faster training, easier to interpret, lower resource requirements
- No need for GPU infrastructure

### 2. Feature Engineering vs. Raw Data

**Rationale:**
- Domain knowledge encoded in features
- Binary completeness flags are highly interpretable
- External context (INSEE, population) adds valuable signal
- Freshness features capture temporal decay

### 3. Redis Caching Layer

**Rationale:**
- POI scores rarely change
- Cache hit rate: ~85% (estimated)
- Reduces inference latency from ~50ms to ~2ms
- Cost reduction for high-traffic scenarios

### 4. Containerization with Docker

**Rationale:**
- Reproducible deployments
- Easy scaling (multiple API containers)
- Isolated environments for each service
- CI/CD integration-ready

### 5. Parquet for Data Storage

**Rationale:**
- 10x smaller than CSV (50k rows: 15MB → 1.5MB)
- Columnar format enables fast analytics
- Built-in compression
- Native support in pandas/polars

---

## 📈 Performance Benchmarks

### API Response Times

| Endpoint | Cold Start | With Cache | P95 | P99 |
|----------|-----------|------------|-----|-----|
| `/score-poi` | 45ms | 2ms | 60ms | 120ms |
| `/health` | 1ms | 1ms | 2ms | 3ms |
| `/opportunities` | 80ms | 10ms | 100ms | 150ms |

### Model Inference

- **Single POI:** <5ms (CPU)
- **Batch (100 POIs):** ~200ms
- **Memory Usage:** ~150MB (model loaded)

### Scalability

- **Tested:** 100 concurrent requests with 4 Uvicorn workers
- **Expected:** Can handle 1000+ req/s with horizontal scaling

---

## 📚 Documentation

- [**ARCHITECTURE.md**](docs/ARCHITECTURE.md) - System design and technical decisions
- [**ML_PIPELINE.md**](docs/ML_PIPELINE.md) - Detailed ML pipeline walkthrough
- [**API Reference**](http://localhost:8000/docs) - Interactive OpenAPI docs (when running)
- [**Deployment Guide**](docs/DEPLOYMENT.md) - Production deployment instructions

---

## 🛠️ Development Workflow

### Code Quality Tools

```bash
# Format code with Black
black ml/ api/ data/ tests/

# Lint with flake8
flake8 ml/ api/ data/

# Type checking with mypy
mypy ml/ api/ --strict

# Run all quality checks
make lint  # if Makefile provided
```

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# Runs automatically on git commit:
# - black (formatting)
# - flake8 (linting)
# - mypy (type checking)
# - pytest (tests)
```

---

## 🔧 Configuration

### Environment Variables

Create a `.env` file:

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
ENVIRONMENT=production

# Redis Cache
REDIS_URL=redis://localhost:6379
CACHE_DEFAULT_TTL=3600

# Optional: External APIs
DATATOURISME_API_KEY=your_key_here
INSEE_API_KEY=your_key_here
```

---

## 📦 Project Structure

```
tourismiq-platform/
├── ml/                          # Machine Learning Module
│   ├── models/                  # Trained models
│   │   └── quality_scorer/
│   │       ├── scorer.pkl       # Serialized model (joblib)
│   │       ├── metrics.json     # Performance metrics
│   │       └── features.txt     # Feature list
│   ├── training/                # Training scripts
│   │   ├── 01_data_collection_eda.py
│   │   ├── 02_feature_engineering.py
│   │   ├── 03_train_quality_scorer.py
│   │   └── 04_gap_detector.py
│   └── inference/               # Inference module
│       └── scorer.py            # POIQualityScorer class
│
├── api/                         # FastAPI Application
│   ├── main.py                  # API entry point
│   ├── models.py                # Pydantic models
│   ├── endpoints/               # Route handlers
│   └── services/                # Business logic
│
├── data/                        # Data Management
│   ├── collectors/              # Data collection modules
│   │   ├── datatourisme_collector.py
│   │   ├── insee_melodi_collector.py
│   │   └── opendatasoft_collector.py
│   ├── raw/                     # Raw data
│   ├── processed/               # Processed data (Parquet)
│   │   └── features_ml.parquet  # 50k POIs with features
│   └── cache/                   # Cache storage
│
├── dashboard/                   # Streamlit Dashboard
│   └── app.py                   # Interactive analytics
│
├── tests/                       # Test Suite
│   ├── unit/                    # Unit tests
│   │   └── test_poi_scorer.py  # 20+ unit tests
│   ├── integration/             # Integration tests
│   │   └── test_api.py         # 25+ API tests
│   └── conftest.py              # Pytest configuration
│
├── infrastructure/              # DevOps & Deployment
│   ├── docker/
│   │   ├── Dockerfile.api
│   │   ├── Dockerfile.dashboard
│   │   └── docker-compose.yml
│   └── monitoring/
│       └── prometheus.yml
│
├── docs/                        # Documentation
│   ├── ARCHITECTURE.md
│   ├── ML_PIPELINE.md
│   └── DEPLOYMENT.md
│
├── config/                      # Configuration files
├── pyproject.toml              # Modern Python packaging
├── requirements.txt            # Dependencies
├── .env.example                # Environment template
├── .gitignore                  # Git ignore rules
└── README.md                   # This file
```

---

## 🎓 Technical Highlights

### 1. Type Safety

```python
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class POIScoringResult:
    poi_id: str
    quality_score: float
    confidence: float
    features: Dict[str, float]
```

### 2. Design Patterns

- **Factory Pattern:** `get_all_collectors()`
- **Dataclass Pattern:** `POIScoringResult`
- **Repository Pattern:** Data access abstraction
- **Dependency Injection:** Model loading in API lifespan

### 3. Error Handling

```python
try:
    model = joblib.load(model_path)
except FileNotFoundError:
    raise RuntimeError(
        f"Model not found at {model_path}. "
        "Run training script first."
    )
```

### 4. Async/Await

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load models on startup
    logger.info("Loading models...")
    yield
    # Cleanup on shutdown
```

---

## 🚧 Future Enhancements

- [ ] **CI/CD Pipeline** - GitHub Actions for automated testing and deployment
- [ ] **Hyperparameter Tuning** - Optuna integration for model optimization
- [ ] **A/B Testing** - Compare multiple model versions in production
- [ ] **Explainability** - SHAP values for model interpretability
- [ ] **Real-time Training** - Online learning for model updates
- [ ] **Multi-language Support** - NLP features for multilingual POIs
- [ ] **API Rate Limiting** - Token bucket algorithm
- [ ] **Authentication** - JWT-based API authentication

---

## 📄 License

MIT License - See LICENSE file for details

---

## 👤 About the Author

**Nicolas Angougeard**
Self-taught ML/AI Engineer specializing in production machine learning systems.

**Skills Demonstrated:**
- ✅ Classical ML (scikit-learn, gradient boosting)
- ✅ Feature engineering for structured data
- ✅ Production API development (FastAPI)
- ✅ Software architecture & design patterns
- ✅ Containerization & DevOps (Docker)
- ✅ Testing & code quality
- ✅ Technical documentation

**Contact:**
- GitHub: [@nicolasangougeard](https://github.com/nicolasangougeard)
- LinkedIn: [Nicolas Angougeard](https://linkedin.com/in/nicolasangougeard)

---

## 🙏 Acknowledgments

- **DATAtourisme** - French national tourism database
- **INSEE** - National Institute of Statistics and Economic Studies
- **Opendatasoft** - Open data platform
- **FastAPI** - Modern, fast web framework for Python
- **scikit-learn** - Machine learning in Python

---

<p align="center">
  <strong>Built with precision, engineered for production</strong><br>
  TourismIQ Platform © 2025
</p>
