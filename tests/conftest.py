import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "apps", ROOT / "packages"):
    if str(folder) not in sys.path:
        sys.path.append(str(folder))
