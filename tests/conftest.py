from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from tempfile import mkstemp

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///./test_app.db"

from app.db.base import Base
from app.db.session import get_db_session
from app.main import app


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    file_descriptor, raw_path = mkstemp(suffix=".db")
    os.close(file_descriptor)
    database_path = Path(raw_path)
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    Base.metadata.create_all(bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        if database_path.exists():
            database_path.unlink()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db_session():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_get_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {
        "X-Auth-Workspace-Id": "ws_1",
        "X-Auth-User-Id": "usr_actor",
        "X-Auth-Actions": "approval:read,approval:create,approval:decide,approval:cancel",
    }
