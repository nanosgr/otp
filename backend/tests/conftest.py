import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models.models  # noqa: F401  (registra las tablas en SQLModel.metadata)
import app.models.prevision  # noqa: F401


@pytest.fixture
def db():
    """Sesión sobre SQLite in-memory con el esquema completo creado."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)
