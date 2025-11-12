"""
TourismIQ Platform - Machine Learning Module
===========================================

This module contains the complete ML pipeline for tourism POI quality scoring:
- Feature engineering
- Model training (Gradient Boosting)
- Model inference
- Gap detection algorithms

Author: Nicolas Angougeard
"""

__version__ = "1.0.0"
__author__ = "Nicolas Angougeard"

from .inference.scorer import POIQualityScorer

__all__ = ["POIQualityScorer"]
