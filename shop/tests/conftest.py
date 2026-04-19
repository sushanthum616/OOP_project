import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """
    Creates a TestClient with a fresh SQLite DB for every test run.
    Important: we set env vars BEFORE importing/reloading the app modules.
    """
    db_file = tmp_path / "test_minishop.db"
    monkeypatch.setenv("MINISHOP_DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("MINISHOP_SECRET_KEY", "test-secret")

    # Reload db + main so they pick up the test DB URL
    import backend.app.db as dbmod
    import backend.app.main as mainmod

    importlib.reload(dbmod)
    importlib.reload(mainmod)

    with TestClient(mainmod.app) as c:
        yield c