import requests
import json

class LLMService:
    def __init__(self, base_url="http://localhost:1234/v1/chat/completions"):
        self.base_url = base_url

    def generate_response(self, prompt: str):
        # LM Studio uses OpenAI format
        payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful hotel booking assistant. Answer in plain text dont include any asteriks etc. Keep your responses concise and friendly."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": -1,
            "stream": False
        }
        try:
            response = requests.post(self.base_url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error connecting to LM Studio: {str(e)}"
