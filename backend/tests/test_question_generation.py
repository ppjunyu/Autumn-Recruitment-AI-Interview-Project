import pytest

from app.chunking import chunk_document
from app.parsers import extract_text
from app.keyword_retrieve import build_prompt, keywords_from, retrieve_for_candidate
from app.qwen_client import parse_json_object, qwen_settings


def test_chunk_drops_short_and_duplicate_paragraphs():
    text = """# 计价规则

电费按抄表读数和阶梯单价计算，异常标记包括缺失读数。

# 短

太短

# 计价规则

电费按抄表读数和阶梯单价计算，异常标记包括缺失读数。
"""
    pieces = chunk_document(text)
    assert len(pieces) == 1
    assert pieces[0]["heading"] == "计价规则"


def test_keyword_recall_then_filter_then_topk():
    chunks = [
        {"id": "other", "text": "电费核算接口需要幂等", "company": "别的公司", "department": "营销部", "position": "电费核算后端开发", "kind": "position_material", "document_id": "d1"},
        {"id": "unselected", "text": "电费核算的内部操作手册还写了阶梯单价", "company": "山东鲁软", "department": "营销部", "position": "电费核算后端开发", "kind": "position_material", "document_id": "d2"},
        {"id": "bank", "text": "电费核算题：请说明重复提醒和业务单号", "company": "山东鲁软", "department": "营销部", "position": "电费核算后端开发", "kind": "question_bank", "document_id": "d3"},
        {"id": "selected", "text": "电费核算规则：抄表读数乘以阶梯单价", "company": "山东鲁软", "department": "营销部", "position": "电费核算后端开发", "kind": "position_material", "document_id": "d4"},
    ]
    words = keywords_from("电费核算 阶梯单价 重复提醒")
    hits = retrieve_for_candidate(
        chunks,
        words,
        company="山东鲁软",
        department="营销部",
        position="电费核算后端开发",
        selected_document_ids=["d4"],
        k=5,
    )
    ids = [item["id"] for item in hits]
    assert "other" not in ids
    assert "unselected" not in ids
    assert "bank" in ids
    assert "selected" in ids


def test_prompt_contains_retrieved_chunk():
    prompt = build_prompt(
        {"name": "周宁", "company": "山东鲁软", "department": "营销部", "position": "电费核算后端开发", "resume_text": "做过对账"},
        {"responsibilities": "做接口", "requirements": "熟悉计价"},
        "幂等",
        [{"id": "c1", "heading": "欠费提醒", "text": "失败重试必须带业务单号"}],
        {"basic_count": 1, "skill_count": 1, "easy_count": 1, "medium_count": 1, "hard_count": 0, "basic_minutes": 10, "skill_minutes": 30},
    )
    assert "c1" in prompt
    assert "业务单号" in prompt
    assert "周宁" in prompt


def test_parse_model_json():
    data = parse_json_object('```json\n{"questions":[{"stem":"请说明幂等"}]}\n```')
    assert data["questions"][0]["stem"] == "请说明幂等"


def test_upload_parser_rejects_oversize_and_old_excel():
    with pytest.raises(ValueError, match="5MB"):
        extract_text("rule.txt", b"x" * (5 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="xlsx"):
        extract_text("bank.xls", b"not-a-workbook")
    assert "阶梯" in extract_text("rule.txt", "电费按阶梯单价计算。".encode())


def test_missing_qwen_key_is_reported(monkeypatch):
    monkeypatch.delenv("Qwen_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    assert qwen_settings()["configured"] is False
    from app.qwen_client import generate_json

    with pytest.raises(RuntimeError, match="Qwen_API_KEY"):
        generate_json("出题")
