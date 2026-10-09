import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import DateTime, Integer, String, Text, create_engine, select
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


class InterviewContext(Base):
    __tablename__ = "interview_contexts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    resume_text: Mapped[str] = mapped_column(Text, default="")
    job_description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

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
    
def get_history(client_id: str) -> list[dict]:
    with Session(engine) as session:
        rows = session.scalars(
            select(Interview)
            .where(Interview.client_id == client_id)
            .order_by(Interview.created_at.asc())
            .limit(100)
        ).all()
        return [
            {
                "room_name": r.room_name,
                "role": r.role,
                "interview_type": r.interview_type,
                "created_at": r.created_at.isoformat(),
                "status": r.status,
                "overall_score": r.overall_score,
                "clarity": r.clarity,
                "structure": r.structure,
                "specificity": r.specificity,
                "technical_depth": r.technical_depth,
            }
            for r in rows
        ]



def save_context(resume_text: str, job_description: str) -> str:
    context_id = str(uuid.uuid4())
    with Session(engine) as session:
        session.add(
            InterviewContext(
                id=context_id, resume_text=resume_text, job_description=job_description
            )
        )
        session.commit()
    return context_id


def pop_context(context_id: str) -> dict | None:
    """Read the saved text once, then delete it."""
    with Session(engine) as session:
        row = session.get(InterviewContext, context_id)
        if row is None:
            return None
        data = {"resume_text": row.resume_text, "job_description": row.job_description}
        session.delete(row)
        session.commit()
        return data
    
if __name__ == "__main__":
    init_db()
    print("Tables are ready.")