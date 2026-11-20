"""Compatibility module for backend.recommendation.recommendation_evaluation."""
import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.recommendation import recommendation_evaluation as implementation

sys.modules[__name__] = implementation
