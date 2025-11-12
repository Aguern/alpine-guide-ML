"""
TourismIQ Platform - Data Module
===============================

Data management module handling:
- Data collection from multiple sources
- Data processing and feature engineering
- Data storage (Parquet, databases)
- Data caching strategies

Author: Nicolas Angougeard
"""

__version__ = "1.0.0"

from .collectors import (
    DATAtourismeCollector,
    INSEEMelodiCollector,
    OpendatasoftCollector,
    OpenMeteoCollector,
    get_all_collectors
)

__all__ = [
    "DATAtourismeCollector",
    "INSEEMelodiCollector",
    "OpendatasoftCollector",
    "OpenMeteoCollector",
    "get_all_collectors",
]
