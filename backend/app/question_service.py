import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.embeddings import embed_texts
from app.keyword_retrieve import build_prompt, keywords_from, retrieve_for_candidate
from app.qwen_client import generate_json
from app.recruit_models import (
    BankQuestion,
    Candidate,
    GenerationConfig,
    InterviewQuestion,
    Invitation,
    Job,
    KnowledgeChunk,
    new_id,
)


def _chunks(db: Session) -> list[dict]:
    rows = db.scalars(select(KnowledgeChunk)).all()
    return [
        {
            "id": row.id,
            "document_id": row.document_id,
            "heading": row.heading,
            "text": row.text,
            "company": row.company,
            "department": row.department,
            "position": row.position,
            "kind": row.kind,
        }
        for row in rows
    ]


def _validate(config: dict) -> None:
    total = config["basic_count"] + config["skill_count"]
    if total < 1:
        raise ValueError("至少出 1 道题")
    difficulty = config["easy_count"] + config["medium_count"] + config["hard_count"]
    if difficulty != total:
        raise ValueError("初级、中级、高级的数量之和必须等于总题数")


def generate_for_candidate(db: Session, candidate_id: str, config: dict) -> Invitation:
    _validate(config)
    candidate = db.get(Candidate, candidate_id)
    if candidate is None or candidate.screening_status != "passed":
        raise ValueError("人员列表里没有这条已通过评估的记录")
    job = db.get(Job, candidate.job_id)
    words = keywords_from(candidate.position, candidate.resume_text, job.requirements, config.get("focus") or "")
    evidence = retrieve_for_candidate(
        _chunks(db),
        words,
        company=candidate.company,
        department=candidate.department,
        position=candidate.position,
        selected_document_ids=config.get("selected_document_ids") or [],
        k=6,
    )
    prompt = build_prompt(
        {
            "name": candidate.name,
            "company": candidate.company,
            "department": candidate.department,
            "position": candidate.position,
            "resume_text": candidate.resume_text,
        },
        {"responsibilities": job.responsibilities, "requirements": job.requirements},
        config.get("focus") or "",
        evidence,
        config,
    )
    payload = generate_json(prompt)
    if "questions" not in payload:
        raise RuntimeError("模型返回的 JSON 里没有 questions")
    invitation = _store_invitation(db, candidate, config, payload["questions"])
    db.commit()
    db.refresh(invitation)
    invitation.evidence = evidence
    invitation.prompt = prompt
    return invitation


def _apply_config(saved: GenerationConfig, candidate_id: str, config: dict) -> None:
    saved.candidate_id = candidate_id
    saved.basic_minutes = config["basic_minutes"]
    saved.skill_minutes = config["skill_minutes"]
    saved.basic_count = config["basic_count"]
    saved.skill_count = config["skill_count"]
    saved.easy_count = config["easy_count"]
    saved.medium_count = config["medium_count"]
    saved.hard_count = config["hard_count"]
    saved.focus = config.get("focus") or ""
    saved.selected_document_ids = config.get("selected_document_ids") or []


def _store_invitation(db: Session, candidate: Candidate, config: dict, questions: list[dict]) -> Invitation:
    invitation_id = config.get("invitation_id")
    if invitation_id:
        invitation = db.scalar(
            select(Invitation).where(Invitation.id == invitation_id).options(selectinload(Invitation.questions))
        )
        if invitation is None or invitation.candidate_id != candidate.id:
            raise ValueError("这场邀请不属于当前候选人")
        saved = db.get(GenerationConfig, invitation.config_id)
        if saved is None:
            raise ValueError("这场邀请的出题参数不存在")
        _apply_config(saved, candidate.id, config)
        for item in list(invitation.questions):
            db.delete(item)
        db.flush()
        invitation.status = "draft"
        invitation.account = ""
        invitation.password_code = ""
    else:
        saved = GenerationConfig(id=new_id(), candidate_id=candidate.id)
        _apply_config(saved, candidate.id, config)
        invitation = Invitation(id=new_id(), candidate_id=candidate.id, config_id=saved.id, status="draft")
        db.add(saved)
        db.add(invitation)
    for item in questions:
        db.add(
            InterviewQuestion(
                id=new_id(),
                invitation_id=invitation.id,
                kind=item.get("kind") or "skill",
                category=item.get("category") or "",
                stem=item.get("stem") or "",
                difficulty=item.get("difficulty") or "中级",
                minutes=int(item.get("minutes") or 2),
                rubric=item.get("rubric") or [],
                reference_answer=item.get("reference_answer") or "",
                source="ai",
                citation_ids=item.get("citation_ids") or [],
                selected=True,
            )
        )
    return invitation


def index_document_chunks(pieces: list[dict]) -> list[list[float] | None]:
    try:
        return embed_texts([piece["text"] for piece in pieces])
    except RuntimeError:
        raise


def launch(db: Session, invitation: Invitation, question_ids: list[str]) -> Invitation:
    chosen = [item for item in invitation.questions if item.id in set(question_ids)]
    if not chosen:
        raise ValueError("至少勾选一道题")
    for item in invitation.questions:
        item.selected = item.id in set(question_ids)
    invitation.status = "confirmed"
    invitation.account = f"iv{invitation.id[:8]}"
    invitation.password_code = f"{secrets.randbelow(100000000):08d}"
    db.commit()
    db.refresh(invitation)
    return invitation


def save_bank(db: Session, invitation: Invitation, question_ids: list[str]) -> int:
    candidate = invitation.candidate
    chosen = [item for item in invitation.questions if item.id in set(question_ids)]
    if not chosen:
        raise ValueError("至少勾选一道题")
    for item in chosen:
        db.add(
            BankQuestion(
                company=candidate.company,
                department=candidate.department,
                position=candidate.position,
                kind=item.kind,
                category=item.category,
                stem=item.stem,
                difficulty=item.difficulty,
                minutes=item.minutes,
                rubric=item.rubric,
                reference_answer=item.reference_answer,
            )
        )
    db.commit()
    return len(chosen)


def similar_bank(db: Session, question: InterviewQuestion, invitation: Invitation) -> list[dict]:
    candidate = invitation.candidate
    rows = db.scalars(
        select(BankQuestion).where(
            BankQuestion.company == candidate.company,
            BankQuestion.position == candidate.position,
            BankQuestion.kind == question.kind,
        )
    ).all()
    words = keywords_from(question.stem, limit=8)
    scored = []
    for row in rows:
        hits = len([word for word in words if word in row.stem])
        if hits == 0:
            continue
        scored.append(
            {
                "id": row.id,
                "stem": row.stem,
                "similarity": round(hits / max(len(words), 1), 2),
                "use_count": row.use_count,
                "difficulty": row.difficulty,
            }
        )
    scored.sort(key=lambda item: item["similarity"], reverse=True)
    return scored[:8]


def replace_with_bank(db: Session, question: InterviewQuestion, bank_id: str) -> InterviewQuestion:
    bank = db.get(BankQuestion, bank_id)
    if bank is None:
        raise ValueError("题库里没有这道题")
    question.stem = bank.stem
    question.category = bank.category
    question.difficulty = bank.difficulty
    question.minutes = bank.minutes
    question.rubric = bank.rubric
    question.reference_answer = bank.reference_answer
    question.source = "bank"
    question.citation_ids = []
    bank.use_count += 1
    db.commit()
    return question
