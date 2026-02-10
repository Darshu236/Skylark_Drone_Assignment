import os
from typing import Any

import requests


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.1")

    def classify(self, message: str) -> dict[str, Any] | None:
        prompt = f"""
You are a router for a drone-operations assistant.
Return a compact JSON object only, no extra text.
Allowed intents:
- pilots_available
- drones_available
- pilots_in_location
- drones_in_location
- any_available
- assignment_recommend
- assignment_update
- pilot_status_update
- drone_status_update
- pilot_assignment_query
- project_resources
- conflicts
- urgent_reassignment
- greeting
- unknown

Extract fields where possible: project_id, pilot_name, pilot_id, drone_id, status, location, skill, certification, capability.

User message: {message}
JSON:
"""
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("response", "").strip()
            return _safe_json(text)
        except Exception:
            return None

    def answer(self, message: str, context: dict[str, Any]) -> str | None:
        prompt = f"""
You are a helpful assistant for a drone operations coordinator.
Answer the user's question using the provided data context only.
If the answer is not in the data, say you don't know.
Keep it short and clear.

Context (JSON):
{context}

User question: {message}
Answer:
"""
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip() or None
        except Exception:
            return None


def _safe_json(text: str) -> dict[str, Any] | None:
    import json

    try:
        return json.loads(text)
    except Exception:
        # attempt to extract JSON object from text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return None
    return None
