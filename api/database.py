import os
import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger("celesto_ledger")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ledger:ledger@localhost:5432/ledger")

Base = declarative_base()

class RunModel(Base):
    __tablename__ = "runs"

    run_id = Column(String(255), primary_key=True)
    sandbox_name = Column(String(255), unique=True, nullable=False)
    problem_id = Column(String(255), nullable=False)
    state = Column(String(50), nullable=False)
    execution_target = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "run_id": self.run_id,
            "sandbox_name": self.sandbox_name,
            "problem_id": self.problem_id,
            "state": self.state,
            "execution_target": self.execution_target,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

def get_engine():
    # If postgres is reachable, use it. Otherwise fallback to sqlite for test/local resilience.
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            pass
        return engine
    except Exception as e:
        logger.warning(f"Could not connect to configured DATABASE_URL ({DATABASE_URL}): {e}. Using fallback SQLite database.")
        sqlite_url = "sqlite:///./ledger_fallback.db"
        fallback_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
        return fallback_engine

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    # Seed row if table is empty
    db = SessionLocal()
    try:
        existing = db.query(RunModel).filter_by(sandbox_name="sbx-seeddemo1").first()
        if not existing:
            seed = RunModel(
                run_id="run-seed-001",
                sandbox_name="sbx-seeddemo1",
                problem_id="issue-failing-test-repro",
                state="deleted",
                execution_target="celesto_sandbox",
            )
            db.add(seed)
            db.commit()
    finally:
        db.close()
