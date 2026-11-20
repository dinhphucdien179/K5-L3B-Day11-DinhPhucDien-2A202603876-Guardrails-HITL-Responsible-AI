"""Metered NeMo model adapter; deterministic rails remain unchanged."""
from core.api_budget import model_budget
from core.config import get_red_model, get_red_provider


class BudgetedNemoModel:
    def __init__(self, inner):
        self.inner = inner

    @property
    def model_name(self):
        return self.inner.model_name

    @property
    def provider_name(self):
        return self.inner.provider_name

    @property
    def provider_url(self):
        return self.inner.provider_url

    async def generate_async(self, prompt, *, stop=None, **kwargs):
        budget = model_budget()
        if budget:
            budget.consume(provider=get_red_provider(), model=self.model_name, purpose="nemo_self_check")
        return await self.inner.generate_async(prompt, stop=stop, **kwargs)

    async def stream_async(self, prompt, *, stop=None, **kwargs):
        budget = model_budget()
        if budget:
            budget.consume(provider=get_red_provider(), model=self.model_name, purpose="nemo_self_check")
        async for item in self.inner.stream_async(prompt, stop=stop, **kwargs):
            yield item


def create_nemo_model():
    import os
    from nemoguardrails.llm.frameworks.default import DefaultFramework
    gemini = get_red_provider() == "gemini"
    kwargs = {"api_key": os.environ.get("GOOGLE_API_KEY" if gemini else "OPENAI_API_KEY"),
              "max_retries": 0, "timeout": 45}
    if gemini:
        kwargs["base_url"] = "https://generativelanguage.googleapis.com/v1beta/openai/"
    inner = DefaultFramework().create_model(get_red_model(), "openai", kwargs)
    return BudgetedNemoModel(inner)
