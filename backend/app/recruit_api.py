from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.chunking import chunk_document
from app.parsers import extract_text
from app.question_service import generate_for_candidate, index_document_chunks, launch, replace_with_bank, save_bank, similar_bank
from app.qwen_client import generate_json, qwen_settings
from app.recruit_db import get_recruit_db
from app.recruit_models import Candidate, InterviewQuestion, Invitation, Job, KnowledgeChunk, KnowledgeDocument, new_id

router = APIRouter(prefix="/api/recruit")


class ConfigIn(BaseModel):
    candidate_id: str
    basic_minutes: int = Field(default=10, ge=0, le=120)
    skill_minutes: int = Field(default=30, ge=10, le=180)
    basic_count: int = Field(default=5, ge=0, le=30)
    skill_count: int = Field(default=10, ge=0, le=30)
    easy_count: int = Field(default=5, ge=0)
    medium_count: int = Field(default=5, ge=0)
    hard_count: int = Field(default=5, ge=0)
    focus: str = ""
    selected_document_ids: list[str] = []
    invitation_id: str | None = None


class LaunchIn(BaseModel):
    question_ids: list[str]


class ReplaceIn(BaseModel):
    bank_id: str


class StemIn(BaseModel):
    stem: str = Field(min_length=4)


class EnterIn(BaseModel):
    account: str
    password_code: str


def require_editor(x_role: str = Header(default="hr")):
    if x_role == "leader":
        raise HTTPException(status_code=403, detail="团队负责人只能查看已生成列表")


def question_dict(row: InterviewQuestion) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "category": row.category,
        "stem": row.stem,
        "difficulty": row.difficulty,
        "minutes": row.minutes,
        "rubric": row.rubric,
        "reference_answer": row.reference_answer,
        "source": row.source,
        "citation_ids": row.citation_ids,
        "selected": row.selected,
    }


def invitation_dict(row: Invitation) -> dict:
    candidate = row.candidate
    basic = [question_dict(item) for item in row.questions if item.kind == "basic"]
    skill = [question_dict(item) for item in row.questions if item.kind != "basic"]
    return {
        "id": row.id,
        "status": row.status,
        "created_at": row.created_at,
        "account": row.account,
        "password_code": row.password_code,
        "login_path": f"/exam/{row.id}",
        "candidate": {
            "id": candidate.id,
            "name": candidate.name,
            "company": candidate.company,
            "department": candidate.department,
            "position": candidate.position,
            "jd_code": candidate.jd_code,
        },
        "basic_questions": basic,
        "skill_questions": skill,
        "basic_count": len(basic),
        "skill_count": len(skill),
    }


def load_invitation(db: Session, invitation_id: str) -> Invitation:
    row = db.scalar(
        select(Invitation)
        .where(Invitation.id == invitation_id)
        .options(selectinload(Invitation.questions), selectinload(Invitation.candidate))
    )
    if row is None:
        raise HTTPException(status_code=404, detail="这场邀请不存在")
    return row


@router.get("/health")
def health():
    settings = qwen_settings()
    return {
        "qwen_configured": settings["configured"],
        "qwen_model": settings["model"],
        "retrieval": "keyword-then-filter",
        "embedding_model": "BAAI/bge-m3",
        "hybrid": False,
        "recall_metric": False,
    }


@router.get("/candidates")
def candidates(db: Session = Depends(get_recruit_db)):
    rows = db.scalars(select(Candidate).where(Candidate.screening_status == "passed")).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "company": row.company,
            "department": row.department,
            "position": row.position,
            "jd_code": row.jd_code,
            "resume_text": row.resume_text,
        }
        for row in rows
    ]


@router.get("/candidates/{candidate_id}")
def candidate_detail(candidate_id: str, db: Session = Depends(get_recruit_db)):
    row = db.get(Candidate, candidate_id)
    if row is None:
        raise HTTPException(status_code=404, detail="人员列表里没有这个人")
    job = db.get(Job, row.job_id)
    return {
        "id": row.id,
        "name": row.name,
        "company": row.company,
        "department": row.department,
        "position": row.position,
        "jd_code": row.jd_code,
        "resume_text": row.resume_text,
        "responsibilities": job.responsibilities,
        "requirements": job.requirements,
    }


@router.get("/documents")
def documents(company: str, department: str, position: str, db: Session = Depends(get_recruit_db)):
    rows = db.scalars(
        select(KnowledgeDocument).where(
            KnowledgeDocument.company == company,
            KnowledgeDocument.department == department,
            KnowledgeDocument.position == position,
        )
    ).all()
    result = []
    for row in rows:
        count = db.scalar(select(func.count()).select_from(KnowledgeChunk).where(KnowledgeChunk.document_id == row.id))
        result.append(
            {
                "id": row.id,
                "kind": row.kind,
                "filename": row.filename,
                "source_label": row.source_label,
                "chunk_count": count or 0,
                "created_at": row.created_at,
            }
        )
    return result


@router.post("/documents")
def upload_document(
    company: str = Form(...),
    department: str = Form(...),
    position: str = Form(...),
    kind: str = Form(...),
    source_label: str = Form("本岗位"),
    file: UploadFile = File(...),
    db: Session = Depends(get_recruit_db),
    _: None = Depends(require_editor),
):
    if kind not in {"position_material", "question_bank"}:
        raise HTTPException(status_code=400, detail="资料类型只能是岗位资料或面试题库")
    payload = file.file.read()
    try:
        text = extract_text(file.filename or "upload.txt", payload)
        pieces = chunk_document(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not pieces:
        raise HTTPException(status_code=400, detail="切块后没有足够长的段落")
    try:
        vectors = index_document_chunks(pieces)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    document = KnowledgeDocument(
        id=new_id(),
        kind=kind,
        company=company,
        department=department,
        position=position,
        filename=file.filename or "upload.txt",
        source_label=source_label,
    )
    db.add(document)
    for piece, vector in zip(pieces, vectors):
        db.add(
            KnowledgeChunk(
                id=new_id(),
                document_id=document.id,
                heading=piece["heading"],
                text=piece["text"],
                content_hash=piece["content_hash"],
                embedding=vector,
                meta={"filename": document.filename, "heading": piece["heading"]},
                company=company,
                department=department,
                position=position,
                kind=kind,
            )
        )
    db.commit()
    return {"id": document.id, "chunk_count": len(pieces)}


@router.post("/generate")
def generate(body: ConfigIn, db: Session = Depends(get_recruit_db), _: None = Depends(require_editor)):
    try:
        invitation = generate_for_candidate(db, body.candidate_id, body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    loaded = load_invitation(db, invitation.id)
    return {
        "steps": [
            "解析 JD 与简历",
            "按关键词召回并过滤",
            "生成基础题",
            "生成专业题",
            "整理评估要点和参考答案",
        ],
        "invitation": invitation_dict(loaded),
    }


@router.get("/invitations")
def invitations(db: Session = Depends(get_recruit_db)):
    rows = db.scalars(
        select(Invitation).options(selectinload(Invitation.questions), selectinload(Invitation.candidate))
    ).all()
    return [invitation_dict(row) for row in rows]


@router.get("/invitations/{invitation_id}")
def invitation_detail(invitation_id: str, db: Session = Depends(get_recruit_db)):
    return invitation_dict(load_invitation(db, invitation_id))


@router.post("/invitations/{invitation_id}/launch")
def launch_invitation(invitation_id: str, body: LaunchIn, db: Session = Depends(get_recruit_db), _: None = Depends(require_editor)):
    row = load_invitation(db, invitation_id)
    try:
        launch(db, row, body.question_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return invitation_dict(load_invitation(db, invitation_id))


@router.post("/invitations/{invitation_id}/save-bank")
def save_invitation_bank(invitation_id: str, body: LaunchIn, db: Session = Depends(get_recruit_db), _: None = Depends(require_editor)):
    row = load_invitation(db, invitation_id)
    try:
        count = save_bank(db, row, body.question_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"saved": count}


@router.post("/invitations/{invitation_id}/enter")
def enter_exam(invitation_id: str, body: EnterIn, db: Session = Depends(get_recruit_db)):
    row = load_invitation(db, invitation_id)
    if row.status != "confirmed" or row.account != body.account or row.password_code != body.password_code:
        raise HTTPException(status_code=401, detail="账号或密码不正确")
    payload = invitation_dict(row)
    payload["password_code"] = ""
    payload["basic_questions"] = [item for item in payload["basic_questions"] if item["selected"]]
    payload["skill_questions"] = [item for item in payload["skill_questions"] if item["selected"]]
    return payload


@router.post("/invitations/{invitation_id}/reset")
def reset_invitation(invitation_id: str, mode: str = "status", db: Session = Depends(get_recruit_db), _: None = Depends(require_editor)):
    row = load_invitation(db, invitation_id)
    if mode == "full":
        db.delete(row)
        db.commit()
        return {"deleted": True}
    row.status = "draft"
    row.account = ""
    row.password_code = ""
    db.commit()
    return invitation_dict(load_invitation(db, invitation_id))


@router.get("/questions/{question_id}/similar")
def similar(question_id: str, db: Session = Depends(get_recruit_db)):
    question = db.get(InterviewQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    invitation = load_invitation(db, question.invitation_id)
    return similar_bank(db, question, invitation)


@router.post("/questions/{question_id}/replace")
def replace(question_id: str, body: ReplaceIn, db: Session = Depends(get_recruit_db), _: None = Depends(require_editor)):
    question = db.get(InterviewQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    try:
        replace_with_bank(db, question, body.bank_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return question_dict(question)


@router.patch("/questions/{question_id}")
def edit_stem(question_id: str, body: StemIn, db: Session = Depends(get_recruit_db), _: None = Depends(require_editor)):
    question = db.get(InterviewQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    if question.source == "bank":
        raise HTTPException(status_code=400, detail="题库原题不能改字，只能替换")
    question.stem = body.stem
    try:
        refreshed = generate_json(
            "根据这道面试题重写评估要点。只返回 JSON："
            '{"rubric":[{"point":"...","weight":1}],"reference_answer":"..."}\n题干：' + body.stem
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    question.rubric = refreshed.get("rubric") or refreshed.get("questions", [{}])[0].get("rubric", [])
    if refreshed.get("reference_answer"):
        question.reference_answer = refreshed["reference_answer"]
    db.commit()
    return question_dict(question)
