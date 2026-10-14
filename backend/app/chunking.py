import hashlib
import re

MIN_CHARS = 20
HEADING = re.compile(r"^(#{1,3}\s+\S.*|[一二三四五六七八九十]+、\S.{0,24}|第[一二三四五六七八九十0-9]+[章节部分]\S{0,24})$")


def _heading(line: str) -> str | None:
    stripped = line.strip()
    if not HEADING.match(stripped):
        return None
    return stripped.lstrip("#").strip()


def chunk_document(text: str) -> list[dict]:
    """按标题和段落切片，丢掉过短和重复的块。"""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    sections: list[tuple[str, list[str]]] = []
    heading = ""
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            sections.append((heading, buffer.copy()))

    for line in lines:
        found = _heading(line)
        if found is not None:
            flush()
            heading = found
            buffer = []
        else:
            buffer.append(line)
    flush()

    pieces: list[dict] = []
    seen: set[str] = set()
    for title, body_lines in sections:
        body = "\n".join(body_lines).strip()
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
        if not paragraphs and body:
            paragraphs = [body]
        for paragraph in paragraphs:
            compact = re.sub(r"\s+", "", paragraph)
            if len(compact) < MIN_CHARS:
                continue
            digest = hashlib.sha256(compact.encode()).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            pieces.append({"heading": title, "text": paragraph.strip(), "content_hash": digest})
    return pieces
