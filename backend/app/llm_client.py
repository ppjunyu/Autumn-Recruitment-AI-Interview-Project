import json
import os
import urllib.error
import urllib.request


def llm_config() -> dict:
    key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    base = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or ""
    model = os.getenv("LLM_MODEL") or ""
    return {
        "configured": bool(key and base and model),
        "model": model or None,
        "missing": [
            name
            for name, value in (
                ("LLM_API_KEY", key),
                ("LLM_BASE_URL", base),
                ("LLM_MODEL", model),
            )
            if not value
        ],
    }


def complete(system: str, user: str) -> str | None:
    """调用 OpenAI 兼容接口。没配齐密钥时返回 None，调用失败时抛出 RuntimeError。"""
    if not llm_config()["configured"]:
        return None
    url = cfg_base_url() + "/chat/completions"
    model = os.getenv("LLM_MODEL") or ""
    body = json.dumps(
        {
            "model": model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
    ).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": "Bearer " + (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.URLError as exc:
        raise RuntimeError(f"大模型接口不可达：{exc}") from exc
    try:
        return payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, AttributeError) as exc:
        raise RuntimeError("大模型返回里没有文本") from exc


def cfg_base_url() -> str:
    base = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or ""
    return base.rstrip("/")
