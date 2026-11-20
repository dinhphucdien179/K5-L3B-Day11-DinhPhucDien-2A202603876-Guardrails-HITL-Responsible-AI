"""Gemini ADK model with one physical attempt per metered invocation."""
from google.adk.models.google_llm import Gemini
from google.genai import types
from core.api_budget import model_budget


class BudgetGemini(Gemini):
    async def generate_content_async(self, llm_request, stream=False):
        budget = model_budget()
        if budget:
            budget.consume(provider="gemini", model=self.model, purpose="red_main")
        async for result in super().generate_content_async(llm_request, stream=stream):
            yield result


def gemini_model(model):
    return BudgetGemini(model=model, retry_options=types.HttpRetryOptions(attempts=1),
                        client_kwargs={"http_options": types.HttpOptions(timeout=45000)})
