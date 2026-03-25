import os
import sys
from unittest.mock import MagicMock

# Add repo root to path so `import Proxy_generator` works when running pytest
# from any directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Must mock DaVinciResolveScript BEFORE any import of Proxy_generator.
# Lines 11-12 of the script execute `resolve = dvr_script.scriptapp("Resolve")`
# at module import time — without this mock, importing the module requires a live
# DaVinci Resolve instance.
_mock_dvr = MagicMock()
_mock_dvr.scriptapp.return_value = MagicMock()
sys.modules["DaVinciResolveScript"] = _mock_dvr
