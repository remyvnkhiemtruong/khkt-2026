import sys
from pathlib import Path

# Ensure workspace root is on sys.path for imports like `import flood_alert_ml`
ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
