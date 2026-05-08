import sys
from pathlib import Path

# Allow `from tutor.x import y` when pytest is run from inside the tutor/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))
