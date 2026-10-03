"""Makes the generated modules importable (`import speech_pb2`) without editing generated files."""
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.append(_here)
