# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys

# The package lives in src/twigpad; make it importable when running tests
# from the project folder without installing it.
SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# Crash-recovery copies made during tests go to a throwaway folder, never to
# the real ~/.local/state/twigpad.
import atexit  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402

from twigpad import recovery  # noqa: E402

recovery.FOLDER = tempfile.mkdtemp(prefix="twigpad-test-recovery-")
atexit.register(shutil.rmtree, recovery.FOLDER, True)
