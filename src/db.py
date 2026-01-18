import datetime
import logging
from contextlib import contextmanager
from urllib.parse import quote_plus

from sqlalchemy import event
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, create_engine

from core import config
from models import Recipe

logger = logging.getLogger(__name__)

# Import so it will auto create tables
import models

odbc = (
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=tcp:database_name_here.database.windows.net,1433;"
    "Database=free-sql-db;"
    "Uid=CloudSAc4b4ac9d;"
    "Pwd=example_password;"
    "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
)
conn_str = f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc)}"
engine = create_engine(conn_str, echo=False, pool_size=10, pool_recycle=1800, pool_pre_ping=True)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Creates tables if they don't already exist
SQLModel.metadata.create_all(engine)


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
    except Exception:
        logger.exception(f"Error with session.")
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
