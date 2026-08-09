import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://cfr_user:cfr_password_2026@localhost:5432/cfr_dispatch"
)

# Convert asyncpg/postgresql scheme if needed
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

try:
    if "sqlite" in DATABASE_URL:
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    else:
        # Test PostgreSQL connection with quick timeout
        test_engine = create_engine(DATABASE_URL, pool_timeout=2, connect_args={"connect_timeout": 2})
        with test_engine.connect():
            pass
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_recycle=1800,
            pool_timeout=30
        )
        logging.info("Connected to containerized PostgreSQL database.")
except Exception as db_err:
    logging.warning(f"PostgreSQL connection failed ({db_err}). Falling back to local SQLite database for development.")
    db_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(db_dir, exist_ok=True)
    sqlite_url = f"sqlite:///{os.path.join(db_dir, 'cfr_dispatch.db').replace('\\', '/')}"
    engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})



SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
