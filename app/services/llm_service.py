import httpx
import json


class LLMService:
    def __init__(self, base_url="http://localhost:1234/v1/chat/completions"):
        self.base_url = base_url
        self.system_prompt = (
            "You are Aria, a warm and professional hotel booking assistant for LuxeStay. "
            "Keep responses concise and friendly. Respond in short, clear sentences."
            "Respond in plain text only. No markdown. No emojis"
        )

    async def stream_response(self, prompt: str):
        """Async generator — yields LLM tokens one by one via LM Studio SSE."""
        payload = {
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 512,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", self.base_url, json=payload) as response:
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError):
                        continue
