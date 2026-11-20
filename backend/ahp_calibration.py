"""Compatibility module for extra.research_tools.ahp_calibration."""
import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from extra.research_tools import ahp_calibration as implementation

if __name__ == "__main__":
    implementation.main()
else:
    sys.modules[__name__] = implementation
