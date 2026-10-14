import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.recruit_models import RecruitBase

SessionLocal = None
engine = None


def database_url() -> str:
    return os.getenv("RECRUIT_DATABASE_URL", "")


def init_recruit_db():
    global engine, SessionLocal
    url = database_url()
    if not url:
        return None
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    RecruitBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine


def get_recruit_db():
    if SessionLocal is None:
        init_recruit_db()
    if SessionLocal is None:
        raise RuntimeError("未设置 RECRUIT_DATABASE_URL")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
