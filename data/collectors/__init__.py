"""
TourismIQ Platform - Data Collectors Module
==========================================

Unified data collection module that aggregates data from multiple sources:
- DATAtourisme: French national tourism database
- INSEE MELODI: Salary and socio-economic data
- Opendatasoft: Population and geographic data
- OpenMeteo: Weather and climate data

Architecture:
- Each collector implements a standard interface
- Collectors handle rate limiting and error recovery
- Data is validated before storage
- Supports both batch and real-time collection

Author: Nicolas Angougeard
"""

from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import collectors from ingestion module
from data.ingestion.datatourisme_collector import DATAtourismeCollector
from data.ingestion.insee_melodi_collector import INSEEMelodiCollector
from data.ingestion.opendatasoft_collector import OpendatasoftCollector
from data.ingestion.openmeteo_collector import OpenMeteoCollector

__version__ = "1.0.0"

__all__ = [
    "DATAtourismeCollector",
    "INSEEMelodiCollector",
    "OpendatasoftCollector",
    "OpenMeteoCollector",
]


def get_all_collectors():
    """
    Factory function to instantiate all available collectors.

    Returns:
        Dict[str, BaseCollector]: Dictionary of collector name to collector instance
    """
    return {
        "datatourisme": DATAtourismeCollector(),
        "insee": INSEEMelodiCollector(),
        "opendatasoft": OpendatasoftCollector(),
        "openmeteo": OpenMeteoCollector(),
    }
