from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def upgrade_workflow_schema():
    """Idempotently extends the existing PostgreSQL schema for the workflow."""
    statements = [
        "ALTER TABLE applications ADD COLUMN IF NOT EXISTS applicant_id INTEGER REFERENCES users(id)",
        "ALTER TABLE applications ADD COLUMN IF NOT EXISTS assigned_inspector_id INTEGER REFERENCES users(id)",
        "ALTER TABLE applications ADD COLUMN IF NOT EXISTS scheduled_for TIMESTAMP",
        "ALTER TABLE applications ADD COLUMN IF NOT EXISTS scheduling_notes TEXT",
        "ALTER TABLE applications ADD COLUMN IF NOT EXISTS decision_reason TEXT",
        "ALTER TABLE applications ADD COLUMN IF NOT EXISTS decision_by INTEGER REFERENCES users(id)",
        "ALTER TABLE applications ADD COLUMN IF NOT EXISTS decision_at TIMESTAMP",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS measurement_unit VARCHAR(50)",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS test_information TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS observations TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS evidence_reference TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS inspector_id INTEGER REFERENCES users(id)",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS inspector_email VARCHAR(255)",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMP",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
