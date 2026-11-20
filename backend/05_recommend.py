"""Explicit operational MCDA CLI compatibility entry point."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.recommendation.mcda_engine import main
if __name__ == "__main__":
    main()
