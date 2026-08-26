"""Make ``viewer`` importable when running pytest straight from the checkout.

Installing the project (``pip install -e .``) makes this unnecessary, but the
tests should run on a bare clone with only the dependencies present.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
