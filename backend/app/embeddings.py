"""bge-m3 嵌入。模型在用户的 WSL 上加载，不在导入时下载。"""

import os

_model = None


def model_name() -> str:
    return os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    global _model
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("本机还没安装 sentence-transformers，无法加载 bge-m3") from exc
    if _model is None:
        device = os.getenv("EMBEDDING_DEVICE", "cuda")
        kwargs = {}
        if device.startswith("cuda"):
            import torch

            kwargs["model_kwargs"] = {"torch_dtype": torch.float16}
        _model = SentenceTransformer(model_name(), device=device, **kwargs)
    vectors = _model.encode(texts, normalize_embeddings=True)
    rows = [vector.tolist() for vector in vectors]
    width = len(rows[0]) if rows else 0
    if width != 1024:
        raise RuntimeError(f"当前嵌入维度是 {width}，库字段按 bge-m3 的 1024 维建立")
    return rows
