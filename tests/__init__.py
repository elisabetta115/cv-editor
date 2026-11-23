# The tests import their helpers as "support", however they are started:
#   python3 -m unittest                      (every test, from the project folder)
#   python3 -m unittest tests/test_render.py (one file)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
