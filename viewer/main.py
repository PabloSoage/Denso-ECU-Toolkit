"""Backwards-compatible launcher for ``python viewer/main.py``.

The supported invocation is ``python -m viewer`` (or the ``denso-viewer``
console script). Running this file directly still works: it puts the project
root on ``sys.path`` first so the package imports resolve.
"""

import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from viewer.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
