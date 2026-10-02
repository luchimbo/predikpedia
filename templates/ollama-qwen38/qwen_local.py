"""Minimal client for the shared Ollama Qwen 3.8 server."""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url=os.environ["LLM_LOCAL_BASE_URL"].rstrip("/"),
    api_key=os.environ["LLM_LOCAL_API_KEY"],
)


def ask(prompt: str, system_prompt: str = "Sos un asistente útil.") -> str:
    response = client.chat.completions.create(
        model=os.environ.get("LLM_LOCAL_MODEL", "qwen3.8:latest"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        timeout=120,
    )
    return response.choices[0].message.content or ""


if __name__ == "__main__":
    print(ask("Respondé solamente: conexión correcta."))
