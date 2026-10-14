import re

SPLIT = re.compile(r"[，。；、,.;：:\s/（）()【】\[\]《》<>]+")


def keywords_from(*parts: str, limit: int = 16) -> list[str]:
    """从候选人、岗位和考察重点里抽出查询词。一条检索路径，不是多路召回。"""
    found: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        for raw in SPLIT.split(part):
            token = raw.strip()
            if not 2 <= len(token) <= 18:
                continue
            if token in seen:
                continue
            seen.add(token)
            found.append(token)
            if len(found) >= limit:
                return found
    return found


def keyword_recall(chunks: list[dict], words: list[str]) -> list[dict]:
    hits = []
    for chunk in chunks:
        text = chunk.get("text") or ""
        matched = [word for word in words if word and word in text]
        if not matched:
            continue
        hits.append({**chunk, "matched": matched, "keyword_hits": len(matched)})
    return hits


def filter_chunks(
    chunks: list[dict],
    *,
    company: str,
    department: str,
    position: str,
    selected_document_ids: list[str],
) -> list[dict]:
    """召回之后再按岗位过滤。未勾选的岗位资料不进入提示词；同一岗位的题库保留。"""
    selected = set(selected_document_ids)
    kept = []
    for chunk in chunks:
        if chunk.get("company") != company or chunk.get("department") != department or chunk.get("position") != position:
            continue
        kind = chunk.get("kind")
        document_id = str(chunk.get("document_id") or "")
        if kind == "question_bank":
            kept.append(chunk)
        elif document_id in selected:
            kept.append(chunk)
    return kept


def topk(chunks: list[dict], k: int = 6) -> list[dict]:
    ranked = sorted(chunks, key=lambda item: item.get("keyword_hits", 0), reverse=True)
    return ranked[:k]


def retrieve_for_candidate(chunks: list[dict], words: list[str], *, company: str, department: str, position: str, selected_document_ids: list[str], k: int = 6) -> list[dict]:
    recalled = keyword_recall(chunks, words)
    filtered = filter_chunks(
        recalled,
        company=company,
        department=department,
        position=position,
        selected_document_ids=selected_document_ids,
    )
    return topk(filtered, k)


def build_prompt(candidate: dict, job: dict, focus: str, evidence: list[dict], config: dict) -> str:
    blocks = []
    for index, item in enumerate(evidence, start=1):
        blocks.append(
            f"[{item.get('id')}] 标题：{item.get('heading') or '无'}\n{item.get('text')}"
        )
    evidence_text = "\n\n".join(blocks) if blocks else "（本次没有勾选岗位资料，也没有命中题库片段。）"
    return f"""你是企业招聘初试的出题人。只根据下面的岗位、简历和检索片段出题，不要编造候选人没写过的项目。
每道题必须返回 JSON。引用片段使用检索片段的 id，没有片段时 citation_ids 为空数组。

候选人：{candidate['name']}
公司：{candidate['company']}　部门：{candidate['department']}　岗位：{candidate['position']}
考察重点：{focus or '无'}

岗位职责：
{job['responsibilities']}

岗位要求：
{job['requirements']}

简历：
{candidate['resume_text']}

检索片段：
{evidence_text}

题量：基本信息题 {config['basic_count']} 道，专业技能题 {config['skill_count']} 道。
难度：初级 {config['easy_count']}、中级 {config['medium_count']}、高级 {config['hard_count']}。
基本信息总时长约 {config['basic_minutes']} 分钟，专业技能总时长约 {config['skill_minutes']} 分钟。
基本信息类别从稳定性、沟通协作、抗压、学习自驱里选。岗位名称含「管理」或「负责人」时可以出团队领导力。
专业类别从业务知识、项目经验、技术深度、工具系统里选。岗位需要方案能力时再出综合方案。

只返回 JSON，形如：
{{"questions":[{{"kind":"basic","category":"沟通协作","stem":"...","difficulty":"中级","minutes":2,"rubric":[{{"point":"...","weight":1}}],"reference_answer":"...","citation_ids":["片段id"]}}]}}
"""
