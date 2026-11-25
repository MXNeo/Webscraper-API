import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Isolate side effects of importing main (config files, metrics DB) before it is imported
_TMP = tempfile.mkdtemp(prefix="webscraper-tests-")
os.environ["CONFIG_DIR"] = os.path.join(_TMP, "config")
os.environ["METRICS_DB_PATH"] = os.path.join(_TMP, "data", "metrics.db")
os.environ.pop("AUTH_PASSWORD", None)
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("ALLOW_PRIVATE_URLS", None)
for var in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"):
    os.environ.pop(var, None)
os.chdir(_TMP)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    import main

    with TestClient(main.app) as c:
        yield c
