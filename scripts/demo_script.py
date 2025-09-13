from __future__ import annotations

"""Legacy entrypoint that forwards to the improved chat demo.

Kept for compatibility with earlier instructions (README, scripts).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chat_demo import main


if __name__ == "__main__":
    main()
