"""Placeholder AI agent orchestration."""

from .groq_client import chat

class Agent:
    def __init__(self):
        pass

    def recommend(self, prompt: str) -> str:
        return chat(prompt)
