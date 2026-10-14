"""给还没有向量的切片补 bge-m3 嵌入。在 WSL 里执行：python -m app.reindex"""

from sqlalchemy import select

from app.embeddings import embed_texts
from app.envfile import load_env_file
from app.recruit_db import SessionLocal, init_recruit_db
from app.recruit_models import KnowledgeChunk


def main() -> None:
    load_env_file()
    init_recruit_db()
    if SessionLocal is None:
        raise SystemExit("请先设置 RECRUIT_DATABASE_URL")
    session = SessionLocal()
    rows = session.scalars(select(KnowledgeChunk).where(KnowledgeChunk.embedding.is_(None))).all()
    if not rows:
        print("没有待嵌入的切片")
        return
    vectors = embed_texts([row.text for row in rows])
    for row, vector in zip(rows, vectors):
        row.embedding = vector
        row.meta = {**(row.meta or {}), "embedded": True}
    session.commit()
    print(f"已写入 {len(rows)} 条向量")


if __name__ == "__main__":
    main()
