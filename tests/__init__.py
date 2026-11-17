# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys

# The package lives in src/twigpad; make it importable when running tests
# from the project folder without installing it.
SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
