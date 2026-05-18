import httpx
import json
import os
from dotenv import load_dotenv

load_dotenv()


class LLMService:
    # Previous LM Studio base_url (Commented out):
    # def __init__(self, base_url="http://localhost:1234/v1/chat/completions"):
    #     self.base_url = base_url
    
    def __init__(self, base_url="https://api.groq.com/openai/v1/chat/completions"):
        self.base_url = base_url
        self.api_key = os.getenv("GROQ_API_KEY")
        self.system_prompt = (
            "You are Alice, a warm and professional hotel booking assistant for LuxeStay. "
            "Keep responses concise and friendly. Respond in short, clear sentences. "
            "Respond in plain text only. No markdown. No emojis"
        )

    async def stream_response_llama3_8b(self, prompt: str):
        """Async generator — yields LLM tokens one by one via Groq SSE."""
        # Previous payload for LM Studio (Commented out):
        # payload = {
        #     "messages": [
        #         {"role": "system", "content": self.system_prompt},
        #         {"role": "user", "content": prompt},
        #     ],
        #     "temperature": 0.7,
        #     "max_tokens": 512,
        #     "stream": True,
        # }
        
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 512,
            "stream": True,
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Previous connection client (Commented out):
            # async with client.stream("POST", self.base_url, json=payload) as response:
            async with client.stream("POST", self.base_url, json=payload, headers=headers) as response:
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


    async def stream_response(self, prompt: str):
        """Async generator — yields LLM tokens one by one via Groq SSE."""
        # Previous payload for LM Studio (Commented out):
        # payload = {
        #     "messages": [
        #         {"role": "system", "content": self.system_prompt},
        #         {"role": "user", "content": prompt},
        #     ],
        #     "temperature": 0.7,
        #     "max_tokens": 512,
        #     "stream": True,
        # }
        
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 512,
            "stream": True,
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Previous connection client (Commented out):
            # async with client.stream("POST", self.base_url, json=payload) as response:
            async with client.stream("POST", self.base_url, json=payload, headers=headers) as response:
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


    