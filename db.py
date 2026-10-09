import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import DateTime, Integer, String, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

load_dotenv()

_url = os.environ["DATABASE_URL"]
if _url.startswith("postgresql://"):
    _url = _url.replace("postgresql://", "postgresql+psycopg://", 1)

# pool_pre_ping reconnects automatically if Neon put the database to sleep
engine = create_engine(_url, pool_pre_ping=True)


class Base(DeclarativeBase):
    pass


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    role: Mapped[str] = mapped_column(String(80))
    interview_type: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    status: Mapped[str] = mapped_column(String(20))  # scored | too_short | failed
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clarity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    structure: Mapped[int | None] = mapped_column(Integer, nullable=True)
    specificity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    technical_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transcript: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)


def init_db() -> None:
    Base.metadata.create_all(engine)


def save_interview(**fields) -> None:
    with Session(engine) as session:
        session.add(Interview(**fields))
        session.commit()


def get_report_payload(room_name: str) -> dict | None:
    with Session(engine) as session:
        row = session.scalar(select(Interview).where(Interview.room_name == room_name))
        if row is None:
            return None
        if row.status == "scored":
            return row.report
        return {"error": row.error or "Could not score this interview."}


if __name__ == "__main__":
    init_db()
    print("Tables are ready.")