"""Compatibility module for backend.recommendation.business_aware_mcda."""
import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.recommendation import business_aware_mcda as implementation

sys.modules[__name__] = implementation
