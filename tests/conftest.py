import sys
from pathlib import Path
import pytest

# Ensure project root is on sys.path for imports like `from nlu...`
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def clear_session_memory():
    # Reset in-process session memory between tests for isolation
    try:
        from core.memory import SESSION
        SESSION.clear()
    except Exception:
        pass
