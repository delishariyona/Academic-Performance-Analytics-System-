import pytest

# This is a legacy script-style test module retained for reference.
# Pytest should not collect or run it — skip at module import time.
pytest.skip("legacy script-style tests; skip module during pytest collection", allow_module_level=True)

