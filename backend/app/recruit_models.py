import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return str(uuid.uuid4())


class RecruitBase(DeclarativeBase):
    pass


class Job(RecruitBase):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company: Mapped[str] = mapped_column(String(80))
    department: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(120))
    jd_code: Mapped[str] = mapped_column(String(40))
    responsibilities: Mapped[str] = mapped_column(Text)
    requirements: Mapped[str] = mapped_column(Text)
    preferred: Mapped[str] = mapped_column(Text, default="")
    is_management: Mapped[bool] = mapped_column(Boolean, default=False)


class Candidate(RecruitBase):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    name: Mapped[str] = mapped_column(String(80))
    company: Mapped[str] = mapped_column(String(80))
    department: Mapped[str] = mapped_column(String(80))
    position: Mapped[str] = mapped_column(String(120))
    jd_code: Mapped[str] = mapped_column(String(40))
    resume_text: Mapped[str] = mapped_column(Text)
    screening_status: Mapped[str] = mapped_column(String(32), default="passed")
    job: Mapped[Job] = relationship()


class KnowledgeDocument(RecruitBase):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(32))
    company: Mapped[str] = mapped_column(String(80))
    department: Mapped[str] = mapped_column(String(80))
    position: Mapped[str] = mapped_column(String(120))
    filename: Mapped[str] = mapped_column(String(200))
    source_label: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(cascade="all, delete-orphan")


class KnowledgeChunk(RecruitBase):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id"))
    heading: Mapped[str] = mapped_column(String(200), default="")
    text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    company: Mapped[str] = mapped_column(String(80))
    department: Mapped[str] = mapped_column(String(80))
    position: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(32))


class GenerationConfig(RecruitBase):
    __tablename__ = "generation_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"))
    basic_minutes: Mapped[int] = mapped_column(Integer, default=10)
    skill_minutes: Mapped[int] = mapped_column(Integer, default=30)
    basic_count: Mapped[int] = mapped_column(Integer, default=5)
    skill_count: Mapped[int] = mapped_column(Integer, default=10)
    easy_count: Mapped[int] = mapped_column(Integer, default=5)
    medium_count: Mapped[int] = mapped_column(Integer, default=5)
    hard_count: Mapped[int] = mapped_column(Integer, default=5)
    focus: Mapped[str] = mapped_column(Text, default="")
    selected_document_ids: Mapped[list] = mapped_column(JSONB, default=list)


class Invitation(RecruitBase):
    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"))
    config_id: Mapped[str] = mapped_column(ForeignKey("generation_configs.id"))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    account: Mapped[str] = mapped_column(String(40), default="")
    password_code: Mapped[str] = mapped_column(String(8), default="")
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)
    candidate: Mapped[Candidate] = relationship()
    config: Mapped[GenerationConfig] = relationship()
    questions: Mapped[list["InterviewQuestion"]] = relationship(cascade="all, delete-orphan")


class InterviewQuestion(RecruitBase):
    __tablename__ = "interview_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    invitation_id: Mapped[str] = mapped_column(ForeignKey("invitations.id"))
    kind: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(40))
    stem: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(16))
    minutes: Mapped[int] = mapped_column(Integer, default=2)
    rubric: Mapped[list] = mapped_column(JSONB, default=list)
    reference_answer: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(16), default="ai")
    citation_ids: Mapped[list] = mapped_column(JSONB, default=list)
    selected: Mapped[bool] = mapped_column(Boolean, default=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)


class BankQuestion(RecruitBase):
    __tablename__ = "bank_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company: Mapped[str] = mapped_column(String(80))
    department: Mapped[str] = mapped_column(String(80))
    position: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(40))
    stem: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(16))
    minutes: Mapped[int] = mapped_column(Integer, default=2)
    rubric: Mapped[list] = mapped_column(JSONB, default=list)
    reference_answer: Mapped[str] = mapped_column(Text, default="")
    use_count: Mapped[int] = mapped_column(Integer, default=0)
