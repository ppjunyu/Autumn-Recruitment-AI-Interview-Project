from app.engine import plan_questions, run_turn
from app.sample_data import SAMPLE


def test_questions_quote_resume_material():
    questions = plan_questions(SAMPLE["position"], SAMPLE["jd_text"], SAMPLE["resume_text"])
    fault = next(item for item in questions if item["intent"] == "故障处理")
    assert "幂等" in fault["evidence"]["text"] or "重复提醒" in fault["evidence"]["text"]
    assert fault["evidence"]["text"][:12].replace(" ", "")[:8] in fault["text"] or "简历里写到" in fault["text"]


def test_different_resumes_change_evidence():
    other = "候选人只做过食堂排队叫号，用 Excel 统计窗口等待时间，没有接口开发经历。"
    first = plan_questions(SAMPLE["position"], SAMPLE["jd_text"], SAMPLE["resume_text"])
    second = plan_questions(SAMPLE["position"], SAMPLE["jd_text"], other)
    assert first[0]["evidence"]["text"] != second[0]["evidence"]["text"]


def test_short_answer_is_followed_up_with_quote():
    questions = plan_questions(SAMPLE["position"], SAMPLE["jd_text"], SAMPLE["resume_text"])
    result = run_turn("不知道", questions[0])
    assert result["route"] == "followup"
    assert "不知道" in result["followup_text"]
    assert "decide" in result["trace"]
    assert "followup" in result["trace"]


def test_grounded_answer_is_scored():
    questions = plan_questions(SAMPLE["position"], SAMPLE["jd_text"], SAMPLE["resume_text"])
    question = questions[0]
    evidence = question["evidence"]["text"]
    answer = "我负责的就是这段：" + evidence + "。输入是抄表读数，我做了参数校验和字段映射，用对账文件验收。"
    result = run_turn(answer, question)
    assert result["route"] == "score"
    assert result["score"]["total"] >= 3
    assert result["score"]["engine"] == "rules"


def test_api_flow_reaches_manual_review(client):
    created = client.post("/api/interviews", json=SAMPLE)
    assert created.status_code == 200
    interview_id = created.json()["id"]
    assert "电费" in created.json()["questions"][0]["text"] or "核算" in created.json()["questions"][0]["evidence"]["text"]

    started = client.post(f"/api/interviews/{interview_id}/start")
    assert started.json()["turns"][0]["role"] == "interviewer"

    early = client.post(f"/api/interviews/{interview_id}/report")
    assert early.status_code == 409

    for _ in range(8):
        current = client.get(f"/api/interviews/{interview_id}").json()
        if current["status"] == "ready_for_report":
            break
        answered = client.post(
            f"/api/interviews/{interview_id}/answers",
            json={"answer": "不知道"},
        )
        assert answered.status_code == 200
    finished = client.get(f"/api/interviews/{interview_id}").json()
    assert finished["status"] == "ready_for_report"

    reported = client.post(f"/api/interviews/{interview_id}/report")
    body = reported.json()["report"]
    assert body["engine"] == "rules"
    assert body["llm_chapters"] is False
    assert body["stages"][2]["advice"] == "建议人工复核"


def test_asr_and_dingtalk_are_explicit_blockers(client):
    asr = client.post("/api/asr", files={"file": ("clip.webm", b"not-audio", "audio/webm")})
    assert asr.status_code == 503
    assert "语音识别" in asr.json()["detail"]
    dingtalk = client.get("/api/integrations/dingtalk")
    assert dingtalk.json()["connected"] is False
    health = client.get("/api/health").json()
    assert health["vector_db"] is False
    assert health["celery"] is False
    assert health["llm_configured"] is False
