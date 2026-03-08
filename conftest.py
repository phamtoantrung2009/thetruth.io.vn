import sys
from pathlib import Path

# Allow `import build` to find scripts/build.py
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
