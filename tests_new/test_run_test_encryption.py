import os
import sys
import importlib.util


# Ensure backend module path is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BACKEND_DIR = os.path.join(ROOT, 'backend_v2_withEncryption_withRoles')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def load_test_module():
    path = os.path.join(BACKEND_DIR, 'test_encryption.py')
    spec = importlib.util.spec_from_file_location('backend_test_encryption', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_run_all_encryption_checks():
    """Load the legacy test_encryption.py and run its test_* functions.

    The legacy file uses plain functions returning True/False; this wrapper
    asserts they return truthy values so pytest records coverage on that file.
    """
    mod = load_test_module()

    # Collect names of functions starting with test_
    funcs = [getattr(mod, name) for name in dir(mod) if name.startswith('test_')]
    assert funcs, 'No test_ functions found in test_encryption.py'

    failures = []
    for fn in funcs:
        try:
            res = fn()
        except Exception as e:
            failures.append(f"{fn.__name__} raised {e!r}")
            continue
        if not res:
            failures.append(f"{fn.__name__} returned falsy result")

    if failures:
        raise AssertionError('Legacy tests failed: ' + '; '.join(failures))
