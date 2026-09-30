"""Put Scripts/dev (uepylib, devteam) and Scripts (probes) on sys.path.

Every test module imports this first. Run the suite with

    python3 -m unittest discover -s Scripts/dev/tests
"""

import os
import sys

TESTS = os.path.dirname(os.path.abspath(__file__))
DEV = os.path.dirname(TESTS)
SCRIPTS = os.path.dirname(DEV)
for path in (DEV, SCRIPTS):
    if path not in sys.path:
        sys.path.insert(0, path)
