"""
TourismIQ Platform - API Module
==============================

FastAPI REST API providing:
- POI quality scoring endpoint
- Geographic zone analysis
- Business opportunity detection
- National benchmarking statistics
- Health checks and monitoring

API Design Principles:
- RESTful architecture
- Type-safe with Pydantic models
- Async/await for concurrency
- Proper error handling
- OpenAPI/Swagger documentation
- Health checks for production

Author: Nicolas Angougeard
"""

__version__ = "1.0.0"
__author__ = "Nicolas Angougeard"

from .main import app

__all__ = ["app"]
