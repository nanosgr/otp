import sys
from pathlib import Path

# raíz del repo en sys.path para `import scripts.scaffold...`
_root = Path(__file__).resolve().parents[3]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
