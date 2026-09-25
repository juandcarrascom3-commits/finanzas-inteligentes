"""Global pytest configuration that isolates the backend database before collection."""

import atexit
import os
import shutil
import tempfile


_TEST_DB_DIR = tempfile.mkdtemp(prefix="finance-pytest-")
_TEST_DB_PATH = os.path.abspath(os.path.join(_TEST_DB_DIR, "test.db"))

os.environ["FINANCE_DB_PATH"] = _TEST_DB_PATH
os.environ["FINANCE_SEED_DEMO"] = "1"

atexit.register(shutil.rmtree, _TEST_DB_DIR, ignore_errors=True)
