import logging
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, create_engine, text

from core import config
from models import Recipe

logger = logging.getLogger(__name__)

# Import so it will auto create tables
import models

conn_str = "postgresql+psycopg2://user:password@db:5432/recipes_db"


engine = create_engine(
    conn_str, echo=False, pool_size=10, pool_recycle=1800, pool_pre_ping=True
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def init_db():
    with engine.connect() as connection:
        # Enable the extension manually
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        connection.commit()

    # Now create the tables that depend on pgcrypto functions
    SQLModel.metadata.create_all(engine)


init_db()


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
    except Exception:
        logger.exception("Error with session.")
        session.rollback()
    finally:
        session.close()


@event.listens_for(Recipe, "before_insert")
def _before_insert(mapper, connection, target: Recipe):
    if not target.version:
        target.version = config.version


@event.listens_for(Recipe, "before_update")
def _before_update(mapper, connection, target: Recipe):
    if not target.version:
        target.version = config.version
