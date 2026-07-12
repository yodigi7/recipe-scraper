import logging
from contextlib import contextmanager

from sqlalchemy.orm import sessionmaker
from sqlmodel import create_engine

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
