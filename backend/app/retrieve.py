import re

from rank_bm25 import BM25Okapi

CJK = re.compile(r"[\u4e00-\u9fff]")
WORD = re.compile(r"[a-z0-9_+#.]{2,}", re.I)


def tokens(text: str) -> list[str]:
    """中文用相邻两字，英文用词。不下载分词词典。"""
    lowered = text.lower()
    words = WORD.findall(lowered)
    chars = CJK.findall(text)
    bigrams = [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]
    return words + bigrams


def split_chunks(text: str, source: str) -> list[dict]:
    parts = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    chunks = []
    for index, part in enumerate(parts):
        if len(part) < 8:
            continue
        chunks.append({"source": source, "text": part, "id": f"{source}-{index}"})
    if not chunks and text.strip():
        chunks.append({"source": source, "text": text.strip(), "id": f"{source}-0"})
    return chunks


def search(chunks: list[dict], query: str, k: int = 3) -> list[dict]:
    if not chunks:
        return []
    corpus = [tokens(item["text"]) for item in chunks]
    if all(len(row) == 0 for row in corpus):
        return [{**chunks[0], "bm25": 0.0}]
    model = BM25Okapi(corpus)
    scores = model.get_scores(tokens(query))
    ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
    hits = []
    for index, score in ranked[:k]:
        hits.append({**chunks[index], "bm25": round(float(score), 4)})
    return hits


def overlap(left: str, right: str) -> float:
    a = set(tokens(left))
    b = set(tokens(right))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def quote(text: str, limit: int = 42) -> str:
    compact = re.sub(r"\s+", "", text)
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "…"
