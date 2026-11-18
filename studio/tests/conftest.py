import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The corpus folders and tmp/ (copies made by engine tests) hold scenes, not tests.
collect_ignore_glob = ["corpus/*", "tmp/*"]
