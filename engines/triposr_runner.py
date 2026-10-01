"""Runs TripoSR's run.py. If torchmcubes (needs a C++/CUDA compiler) isn't
installed, a pure-Python stand-in from ./shims is used instead."""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TRIPO = os.path.join(HERE, "TripoSR")
sys.path.insert(0, TRIPO)
try:
    import torchmcubes  # noqa: F401
except ImportError:
    sys.path.insert(0, os.path.join(HERE, "shims"))

sys.argv = [os.path.join(TRIPO, "run.py")] + sys.argv[1:]
runpy.run_path(os.path.join(TRIPO, "run.py"), run_name="__main__")
