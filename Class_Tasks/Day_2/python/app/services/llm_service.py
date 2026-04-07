from langchain_groq import ChatGroq

class LLMService:
    def __init__(self, api_key: str, model: str):
        self.client = ChatGroq(api_key=api_key, model_name=model)

    def generate(self, prompt: str) -> str:
        response = self.client.chat([{"role": "user", "content": prompt}])
        return response.text if hasattr(response, 'text') else str(response)
