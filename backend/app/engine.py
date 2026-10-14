"""初试出题、追问和规则评分。

LangGraph 只编排已经写死的节点。没有大模型密钥时，题目和追问用模板，
模板必须带上检索到的原句或候选人刚说的原话。
"""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.llm_client import complete
from app.retrieve import overlap, quote, search, split_chunks

INTENTS = (
    ("项目职责", "项目 负责 接口 输入 输出", "resume"),
    ("故障处理", "问题 原因 重试 幂等 修复", "resume"),
    ("岗位要求", "要求 业务 对接 规则 数据库", "jd"),
    ("协作沟通", "沟通 现场 业务 联调 排障", "jd"),
)


class PlanState(TypedDict, total=False):
    position: str
    jd_text: str
    resume_text: str
    resume_chunks: list
    jd_chunks: list
    questions: list


class TurnState(TypedDict, total=False):
    answer: str
    question_text: str
    evidence_text: str
    followups_used: int
    route: str
    reason: str
    followup_text: str
    score: dict
    trace: list
    llm_note: str


def _hit(hits: list[dict], rank: int) -> dict:
    if not hits:
        return {"source": "none", "text": "", "bm25": 0.0}
    return hits[min(rank, len(hits) - 1)]


def retrieve_node(state: PlanState) -> dict:
    return {
        "resume_chunks": split_chunks(state["resume_text"], "resume"),
        "jd_chunks": split_chunks(state["jd_text"], "jd"),
    }


def _question_text(intent: str, source: str, snippet: str) -> str:
    if not snippet:
        return "材料里没有对应片段。请直接讲一段和这个岗位最相关的经历，说明你的角色和结果。"
    if intent == "项目职责":
        return f"简历里写到：「{snippet}」。请按当时的情况说明输入是什么、你本人做了哪几步、怎样验收。"
    if intent == "故障处理":
        return f"简历里写到：「{snippet}」。请说明现象、原因，以及你改了什么。"
    if intent == "岗位要求":
        return f"岗位要求里有：「{snippet}」。请举一个你自己做过的例子，不要复述要求本身。"
    return f"岗位写着：「{snippet}」。你当时和谁一起做完，意见不一致时怎么处理？"


def compose_node(state: PlanState) -> dict:
    questions = []
    for index, (intent, query, source) in enumerate(INTENTS):
        pool = state["resume_chunks"] if source == "resume" else state["jd_chunks"]
        hits = search(pool, query, k=1)
        hit = _hit(hits, 0)
        snippet = quote(hit.get("text", ""))
        questions.append(
            {
                "id": f"q{index + 1}",
                "intent": intent,
                "text": _question_text(intent, source, snippet),
                "evidence": {
                    "source": hit.get("source", source),
                    "text": hit.get("text", ""),
                    "bm25": hit.get("bm25", 0.0),
                    "query": query,
                },
                "followups_used": 0,
                "score": None,
            }
        )
    return {"questions": questions}


def build_plan_graph():
    graph = StateGraph(PlanState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("compose", compose_node)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "compose")
    graph.add_edge("compose", END)
    return graph.compile()


PLAN_GRAPH = build_plan_graph()


def plan_questions(position: str, jd_text: str, resume_text: str) -> list[dict]:
    result = PLAN_GRAPH.invoke(
        {"position": position, "jd_text": jd_text, "resume_text": resume_text}
    )
    return result["questions"]


def _score(answer: str, question_text: str, evidence_text: str) -> dict:
    completeness = 0 if len(answer) < 15 else 1 if len(answer) < 40 else 2
    grounding_ratio = overlap(answer, evidence_text)
    grounding = 0 if grounding_ratio < 0.04 else 1 if grounding_ratio < 0.12 else 2
    relevance_ratio = overlap(answer, question_text)
    relevance = 0 if relevance_ratio < 0.04 else 1
    return {
        "total": completeness + grounding + relevance,
        "completeness": completeness,
        "grounding": grounding,
        "relevance": relevance,
        "grounding_overlap": round(grounding_ratio, 4),
        "engine": "rules",
    }


def decide_node(state: TurnState) -> dict:
    trace = list(state.get("trace") or [])
    trace.append("decide")
    score = _score(state["answer"], state["question_text"], state["evidence_text"])
    if state.get("followups_used", 0) >= 1:
        return {"trace": trace, "route": "score", "reason": "这道题已经追问过一次", "score": score}
    if score["completeness"] == 0:
        return {"trace": trace, "route": "followup", "reason": "回答太短，先追问一次", "score": score}
    if score["grounding"] == 0:
        return {
            "trace": trace,
            "route": "followup",
            "reason": "回答和题目引用的材料几乎没有重合，先追问一次",
            "score": score,
        }
    return {"trace": trace, "route": "score", "reason": "回答长度和材料重合足够，进入评分", "score": score}


def _draft_followup(answer: str) -> tuple[str, str]:
    compact = "".join(answer.split())
    snippet = compact[:16] or "这段回答"
    text = f"你刚才说「{snippet}」。请补充三件事：你的角色、关键步骤、怎样判断做完了。"
    return text, snippet


def followup_node(state: TurnState) -> dict:
    trace = list(state.get("trace") or [])
    trace.append("followup")
    draft, snippet = _draft_followup(state["answer"])
    note = "未配置大模型，使用模板追问"
    text = draft
    try:
        rewritten = complete(
            "你是企业初试面试官。只根据候选人刚说的话追问，不超过80字，必须保留给定原话。",
            f"原话：{snippet}\n模板：{draft}\n请改写模板，原话必须原样出现。",
        )
    except RuntimeError as exc:
        rewritten = None
        note = f"大模型调用失败，已退回模板：{exc}"
    if rewritten:
        if snippet in rewritten:
            text = rewritten
            note = "大模型改写了追问，并保留了原话"
        else:
            note = "大模型改写丢掉了原话，已退回模板"
    return {"trace": trace, "followup_text": text, "llm_note": note}


def score_node(state: TurnState) -> dict:
    trace = list(state.get("trace") or [])
    trace.append("score")
    return {"trace": trace, "score": state["score"]}


def route_after_decide(state: TurnState) -> str:
    return state["route"]


def build_turn_graph():
    graph = StateGraph(TurnState)
    graph.add_node("decide", decide_node)
    graph.add_node("followup", followup_node)
    graph.add_node("score", score_node)
    graph.set_entry_point("decide")
    graph.add_conditional_edges(
        "decide",
        route_after_decide,
        {"followup": "followup", "score": "score"},
    )
    graph.add_edge("followup", END)
    graph.add_edge("score", END)
    return graph.compile()


TURN_GRAPH = build_turn_graph()


def run_turn(answer: str, question: dict) -> dict:
    evidence = (question.get("evidence") or {}).get("text") or ""
    result = TURN_GRAPH.invoke(
        {
            "answer": answer,
            "question_text": question["text"],
            "evidence_text": evidence,
            "followups_used": question.get("followups_used", 0),
            "trace": ["ingest"],
        }
    )
    return result


def build_report(interview: dict) -> dict:
    """三阶段是规则汇总，不是多章大模型提示词。"""
    questions = interview["questions"]
    totals = [item["score"]["total"] for item in questions if item.get("score")]
    mean = round(sum(totals) / len(totals), 2) if totals else 0
    per_question = []
    for item in questions:
        score = item.get("score") or {}
        per_question.append(
            {
                "intent": item["intent"],
                "question": item["text"],
                "total": score.get("total"),
                "completeness": score.get("completeness"),
                "grounding": score.get("grounding"),
                "relevance": score.get("relevance"),
                "evidence": (item.get("evidence") or {}).get("text", ""),
            }
        )
    dimensions = {
        "完整度": round(
            sum((item.get("score") or {}).get("completeness", 0) for item in questions) / max(len(questions), 1),
            2,
        ),
        "证据贴合": round(
            sum((item.get("score") or {}).get("grounding", 0) for item in questions) / max(len(questions), 1),
            2,
        ),
        "相关性": round(
            sum((item.get("score") or {}).get("relevance", 0) for item in questions) / max(len(questions), 1),
            2,
        ),
    }
    low_grounding = dimensions["证据贴合"] < 1
    if mean >= 3 and not low_grounding:
        advice = "建议安排复试"
        advice_reason = "规则均分不低于 3，且证据贴合没有明显偏低。这不是录用决定。"
    else:
        advice = "建议人工复核"
        advice_reason = "规则均分偏低，或回答与引用材料重合不足。需要面试官看原始对话。"
    return {
        "engine": "rules",
        "llm_chapters": False,
        "candidate_name": interview["candidate_name"],
        "position": interview["position"],
        "mean_score": mean,
        "stages": [
            {"name": "逐题规则分", "items": per_question},
            {"name": "维度汇总", "dimensions": dimensions},
            {"name": "建议", "advice": advice, "reason": advice_reason},
        ],
        "chapters": [
            {
                "title": "候选人与岗位",
                "body": f"{interview['candidate_name']} 应聘 {interview['position']}。本题库来自简历和岗位说明的字面检索，没有外部知识库。",
            },
            {
                "title": "初试记录",
                "body": f"共 {len(questions)} 道题，规则均分 {mean}（满分 5）。追问最多每题一次，触发条件是回答过短，或与引用材料几乎不重合。",
            },
            {
                "title": "证据与缺口",
                "body": advice_reason + " 生产环境里的多章评估提示词、语音评分和人工分差没有接到这个切片。",
            },
        ],
    }
