import json
import uuid
from contextlib import asynccontextmanager

from app.envfile import load_env_file

load_env_file()

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, engine, get_db
from app.engine import build_report, plan_questions, run_turn
from app.llm_client import llm_config
from app.models import Interview, now_iso
from app.recruit_api import router as recruit_router
from app.sample_data import SAMPLE

Base.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        from app.recruit_db import init_recruit_db

        init_recruit_db()
    except Exception:
        pass
    yield


app = FastAPI(title="招聘面试智能体复刻", lifespan=lifespan)
app.include_router(recruit_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class InterviewIn(BaseModel):
    candidate_name: str = Field(min_length=1, max_length=80)
    position: str = Field(min_length=1, max_length=120)
    jd_text: str = Field(min_length=10)
    resume_text: str = Field(min_length=10)


class AnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)


def dump(interview: Interview) -> dict:
    report = json.loads(interview.report_json) if interview.report_json else None
    return {
        "id": interview.id,
        "candidate_name": interview.candidate_name,
        "position": interview.position,
        "jd_text": interview.jd_text,
        "resume_text": interview.resume_text,
        "status": interview.status,
        "q_index": interview.q_index,
        "questions": json.loads(interview.questions_json),
        "turns": json.loads(interview.turns_json),
        "report": report,
        "created_at": interview.created_at,
    }


def load(db: Session, interview_id: str) -> Interview:
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="这场面试不存在")
    return interview


@app.get("/api/health")
def health():
    llm = llm_config()
    return {
        "retrieval": "bm25-character-bigram",
        "orchestration": "langgraph",
        "llm_configured": llm["configured"],
        "llm_missing": llm["missing"],
        "asr": False,
        "vector_db": False,
        "celery": False,
        "dingtalk": False,
        "blockers": [
            "没有配置 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL，出题和追问走模板。",
            "没有语音识别服务，上传的音频不会转写。",
            "本机没有 PostgreSQL / pgvector，检索是进程内 BM25。",
            "本机没有 Redis，报告在请求里同步生成，没有 Celery。",
            "没有钉钉应用凭证，不能做免登、JSAPI 或 Stream。",
            "没有真实候选人数据，示例简历是虚构的。",
            "机器内存约 16GB 且没有单独的 GPU，不在本地加载 Qwen。",
        ],
    }


@app.get("/api/sample")
def sample():
    return SAMPLE


@app.get("/api/interviews")
def list_interviews(db: Session = Depends(get_db)):
    rows = db.scalars(select(Interview).order_by(Interview.created_at.desc())).all()
    return [dump(row) for row in rows]


@app.post("/api/interviews")
def create_interview(body: InterviewIn, db: Session = Depends(get_db)):
    questions = plan_questions(body.position, body.jd_text, body.resume_text)
    interview = Interview(
        id=str(uuid.uuid4()),
        candidate_name=body.candidate_name.strip(),
        position=body.position.strip(),
        jd_text=body.jd_text.strip(),
        resume_text=body.resume_text.strip(),
        status="planned",
        questions_json=json.dumps(questions, ensure_ascii=False),
        turns_json="[]",
        q_index=0,
        created_at=now_iso(),
    )
    db.add(interview)
    db.commit()
    return dump(interview)


@app.get("/api/interviews/{interview_id}")
def get_interview(interview_id: str, db: Session = Depends(get_db)):
    return dump(load(db, interview_id))


@app.post("/api/interviews/{interview_id}/start")
def start_interview(interview_id: str, db: Session = Depends(get_db)):
    interview = load(db, interview_id)
    if interview.status == "reported":
        raise HTTPException(status_code=409, detail="报告已经生成，这场初试不再作答")
    turns = json.loads(interview.turns_json)
    questions = json.loads(interview.questions_json)
    if not turns:
        first = questions[interview.q_index]
        turns.append(
            {
                "role": "interviewer",
                "content": first["text"],
                "intent": first["intent"],
                "trace": ["compose"],
                "reason": "根据检索到的材料出题",
            }
        )
        interview.turns_json = json.dumps(turns, ensure_ascii=False)
        interview.status = "in_progress"
        db.commit()
    return dump(interview)


@app.post("/api/interviews/{interview_id}/answers")
def answer(interview_id: str, body: AnswerIn, db: Session = Depends(get_db)):
    interview = load(db, interview_id)
    if interview.status == "planned":
        raise HTTPException(status_code=409, detail="先开始面试，再提交回答")
    if interview.status in {"ready_for_report", "reported"}:
        raise HTTPException(status_code=409, detail="题目已经问完")
    questions = json.loads(interview.questions_json)
    turns = json.loads(interview.turns_json)
    if interview.q_index >= len(questions):
        raise HTTPException(status_code=409, detail="题目已经问完")
    question = questions[interview.q_index]
    result = run_turn(body.answer.strip(), question)
    turns.append({"role": "candidate", "content": body.answer.strip()})
    if result["route"] == "followup":
        question["followups_used"] = question.get("followups_used", 0) + 1
        turns.append(
            {
                "role": "interviewer",
                "content": result["followup_text"],
                "intent": question["intent"],
                "trace": result["trace"],
                "reason": result["reason"],
                "llm_note": result.get("llm_note"),
            }
        )
    else:
        question["score"] = result["score"]
        interview.q_index += 1
        if interview.q_index >= len(questions):
            interview.status = "ready_for_report"
            closing = "初试题目已结束。可以生成结构化记录。当前建议来自规则分，不是录用结论。"
        else:
            closing = questions[interview.q_index]["text"]
        turns.append(
            {
                "role": "interviewer",
                "content": closing,
                "intent": question["intent"] if interview.status == "ready_for_report" else questions[interview.q_index]["intent"],
                "trace": result["trace"],
                "reason": result["reason"],
                "score": result["score"],
            }
        )
    interview.questions_json = json.dumps(questions, ensure_ascii=False)
    interview.turns_json = json.dumps(turns, ensure_ascii=False)
    db.commit()
    return dump(interview)


@app.post("/api/interviews/{interview_id}/report")
def report(interview_id: str, db: Session = Depends(get_db)):
    interview = load(db, interview_id)
    if interview.status not in {"ready_for_report", "reported"}:
        raise HTTPException(status_code=409, detail="还有题目没有评分")
    payload = build_report(dump(interview))
    interview.report_json = json.dumps(payload, ensure_ascii=False)
    interview.status = "reported"
    db.commit()
    return dump(interview)


@app.post("/api/asr")
def asr(file: UploadFile = File(...)):
    raise HTTPException(
        status_code=503,
        detail="未配置语音识别。音频已收到但不会转写，请改用文字作答。",
    )


@app.get("/api/integrations/dingtalk")
def dingtalk():
    return {
        "connected": False,
        "sso": False,
        "jsapi": False,
        "stream": False,
        "reason": "没有钉钉应用的 AppKey、AppSecret 和企业租户，无法免登，也无法订阅审批或待办事件。",
    }
