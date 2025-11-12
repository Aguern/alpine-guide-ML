# TourismIQ Platform - Makefile
# Convenient commands for development and deployment

.PHONY: help install test lint format docker-build docker-up docker-down clean

# Default target
help:
	@echo "TourismIQ Platform - Available Commands"
	@echo "========================================"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install          Install dependencies"
	@echo "  make install-dev      Install with dev dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make run-api          Run FastAPI server"
	@echo "  make run-dashboard    Run Streamlit dashboard"
	@echo "  make test             Run test suite"
	@echo "  make test-cov         Run tests with coverage"
	@echo "  make lint             Run linters (flake8, mypy)"
	@echo "  make format           Format code with black"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build     Build Docker images"
	@echo "  make docker-up        Start all services"
	@echo "  make docker-down      Stop all services"
	@echo "  make docker-logs      View logs"
	@echo ""
	@echo "ML Pipeline:"
	@echo "  make train            Train ML model"
	@echo "  make collect-data     Collect data from APIs"
	@echo "  make feature-eng      Run feature engineering"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean            Remove cache and temp files"
	@echo "  make clean-all        Deep clean (including data)"
	@echo ""

# ============================================
# Setup & Installation
# ============================================

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -e ".[dev]"

# ============================================
# Development
# ============================================

run-api:
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

run-dashboard:
	streamlit run dashboard/app.py --server.port 8501

test:
	pytest -v

test-cov:
	pytest --cov=ml --cov=api --cov-report=term-missing --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

lint:
	flake8 ml/ api/ data/ --count --show-source --statistics
	mypy ml/ api/ --ignore-missing-imports

format:
	black ml/ api/ data/ tests/

# ============================================
# Docker
# ============================================

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d
	@echo "Services started:"
	@echo "  - API: http://localhost:8000"
	@echo "  - Dashboard: http://localhost:8501"
	@echo "  - Redis: localhost:6379"

docker-up-monitor:
	docker-compose --profile monitoring up -d
	@echo "Monitoring started:"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - Grafana: http://localhost:3000"

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-restart:
	docker-compose restart

# ============================================
# ML Pipeline
# ============================================

collect-data:
	python ml/training/01_data_collection_eda.py

feature-eng:
	python ml/training/02_feature_engineering.py

train:
	python ml/training/03_train_quality_scorer.py

gap-detection:
	python ml/training/04_gap_detector.py

pipeline-full:
	$(MAKE) collect-data
	$(MAKE) feature-eng
	$(MAKE) train
	@echo "ML pipeline completed!"

# ============================================
# Maintenance
# ============================================

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	@echo "Cleaned cache and temporary files"

clean-all: clean
	rm -rf data/raw/*
	rm -rf data/cache/*
	rm -rf logs/*
	@echo "Deep clean completed"

# ============================================
# Deployment
# ============================================

build-prod:
	docker build -t tourismiq/api:latest -f infrastructure/docker/Dockerfile.api .
	docker build -t tourismiq/dashboard:latest -f infrastructure/docker/Dockerfile.dashboard .

push-prod:
	docker push tourismiq/api:latest
	docker push tourismiq/dashboard:latest

deploy-prod:
	$(MAKE) build-prod
	$(MAKE) push-prod
	@echo "Deployment complete!"

# ============================================
# Documentation
# ============================================

docs-serve:
	@echo "Documentation available at:"
	@echo "  - README: README.md"
	@echo "  - Architecture: docs/ARCHITECTURE.md"
	@echo "  - ML Pipeline: docs/ML_PIPELINE.md"

# ============================================
# Health Checks
# ============================================

health:
	@echo "Checking service health..."
	@curl -f http://localhost:8000/health && echo "✅ API healthy" || echo "❌ API down"
	@curl -f http://localhost:8501/_stcore/health && echo "✅ Dashboard healthy" || echo "❌ Dashboard down"
