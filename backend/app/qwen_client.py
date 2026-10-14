import json
import os
import re

from openai import OpenAI


def qwen_settings() -> dict:
    key = os.getenv("Qwen_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or ""
    return {
        "api_key": key,
        "base_url": os.getenv("QWEN_BASE_URL", "https://maas.qianwenaiapi.com/compatible-mode/v1"),
        "model": os.getenv("QWEN_MODEL", "qwen3.8-flash"),
        "configured": bool(key),
    }


def generate_json(prompt: str) -> dict:
    settings = qwen_settings()
    if not settings["configured"]:
        raise RuntimeError("未读取到环境变量 Qwen_API_KEY，已停止出题，不会用模板冒充模型结果")
    client = OpenAI(api_key=settings["api_key"], base_url=settings["base_url"])
    completion = client.chat.completions.create(
        model=settings["model"],
        messages=[
            {"role": "system", "content": "你只输出一个 JSON 对象，不要输出解释。"},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        extra_body={"enable_thinking": False},
        stream=False,
    )
    content = completion.choices[0].message.content or ""
    return parse_json_object(content)


def parse_json_object(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise RuntimeError("模型返回的不是 JSON 对象")
    return data
