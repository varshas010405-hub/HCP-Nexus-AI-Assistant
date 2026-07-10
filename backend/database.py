import os
import logging
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/hcp_nexus_db")

# Fallback to SQLite if PostgreSQL is not available, to allow seamless testability
try:
    # Test if we can configure PostgreSQL
    if DATABASE_URL.startswith("postgresql"):
        logger.info(f"Attempting to configure PostgreSQL database engine...")
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        # Try a quick connection to check if it's running
        with engine.connect() as conn:
            logger.info("Successfully connected to PostgreSQL database!")
    else:
        logger.info("Configuring engine with SQLite (URL doesn't start with postgresql)")
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
except Exception as e:
    logger.warning(f"Failed to connect to PostgreSQL database: {e}. Falling back to SQLite local db...")
    SQLite_URL = "sqlite:///./hcp_nexus.db"
    engine = create_engine(SQLite_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_sqlite_schema():
    """Apply lightweight SQLite schema adjustments for older local databases."""
    if engine.url.get_backend_name() != "sqlite":
        return

    with engine.begin() as conn:
        inspector = inspect(conn)
        if "interactions" not in inspector.get_table_names():
            return

        columns = {column["name"] for column in inspector.get_columns("interactions")}
        if "user_id" not in columns:
            conn.execute(text("ALTER TABLE interactions ADD COLUMN user_id INTEGER"))
            logger.info("Added missing user_id column to interactions table for SQLite compatibility.")

# Dependency to get db session in endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
