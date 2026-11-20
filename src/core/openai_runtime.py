"""OpenAI-compatible runtime for Blue/OpenRouter and Red/OpenAI."""
from __future__ import annotations

import inspect
import time
import uuid
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Callable

from core.api_budget import BudgetExceeded, model_budget, safe_error
from core.config import (get_red_model, get_red_provider, get_blue_model,
                         get_blue_provider, blue_client_kwargs, red_openai_client_kwargs)


@dataclass
class OpenAIAgent:
    name: str
    instruction: str
    provider: str = "openai"


@dataclass
class ChatOutcome:
    text: str
    blocked: bool = False
    layer: str | None = None
    redacted: bool = False
    error: str | None = None
    latency_ms: float = 0
    request_id: str = ""
    user_id: str = "student"
    session: Any = None


async def _callback(cb, **kwargs):
    result = cb(**kwargs)
    return await result if inspect.isawaitable(result) else result


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "".join(getattr(p, "text", "") or "" for p in (getattr(content, "parts", None) or []))


@dataclass
class OpenAIRunner:
    app_name: str
    model: str
    plugins: list = field(default_factory=list)
    provider: str = "openai"
    temperature: float = 0.4
    client_kwargs: dict = field(default_factory=dict)
    input_hooks: list[Callable] = field(default_factory=list)
    output_hooks: list[Callable] = field(default_factory=list)
    _sessions: dict = field(default_factory=dict, repr=False)

    def _client(self):
        from openai import OpenAI
        return OpenAI(**self.client_kwargs, max_retries=0, timeout=45)

    async def chat(self, agent, user_message, *, user_id="student", request_id=None, session_id=None):
        result = await self.chat_detailed(agent, user_message, user_id=user_id,
                                         request_id=request_id, session_id=session_id)
        if result.error:
            raise RuntimeError(result.error)
        return result.text

    async def chat_detailed(self, agent, user_message, *, user_id="student", request_id=None, session_id=None):
        from google.genai import types
        started = time.monotonic()
        request_id = request_id or uuid.uuid4().hex
        sid = getattr(session_id, "id", session_id) or uuid.uuid4().hex
        key = (user_id, sid)
        history = self._sessions.setdefault(key, [])
        metadata = {}
        ctx = SimpleNamespace(user_id=user_id, request_id=request_id, metadata=metadata)
        result = ChatOutcome("", request_id=request_id, user_id=user_id, session=SimpleNamespace(id=sid))
        stage = "input_guardrail"
        try:
            for hook in self.input_hooks:
                blocked = hook(user_message)
                if blocked is not None:
                    result.text, result.blocked, result.layer = blocked, True, stage
                    return result
            user_content = types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
            for plugin in self.plugins:
                cb = getattr(plugin, "on_user_message_callback", None)
                if cb is None:
                    continue
                content = await _callback(cb, invocation_context=ctx, user_message=user_content)
                if content is not None:
                    result.text = _content_to_text(content)
                    result.blocked = True
                    result.layer = metadata.get("layer", getattr(plugin, "name", stage))
                    return result
            stage = "provider"
            budget = model_budget()
            if budget:
                budget.consume(provider=self.provider, model=self.model, purpose=self.app_name)
            messages = [{"role": "system", "content": agent.instruction}, *history,
                        {"role": "user", "content": user_message}]
            completion = self._client().chat.completions.create(
                model=self.model, messages=messages, temperature=self.temperature)
            text = (completion.choices[0].message.content or "").strip()
            if not text:
                raise ValueError("Empty model response")
            stage = "output_guardrail"
            for hook in self.output_hooks:
                text = hook(text)
            response = SimpleNamespace(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))
            for plugin in self.plugins:
                cb = getattr(plugin, "after_model_callback", None)
                if cb:
                    out = await _callback(cb, callback_context=ctx, llm_response=response)
                    if out is not None:
                        response = out
            result.text = _content_to_text(response.content)
            result.blocked = metadata.get("blocked", False)
            result.layer = metadata.get("layer")
            result.redacted = metadata.get("redacted", False)
            history.extend([{"role": "user", "content": user_message}, {"role": "assistant", "content": result.text}])
        except BudgetExceeded:
            raise
        except Exception as exc:
            result.error = safe_error(exc)
            result.layer = "error" if stage == "provider" else "guardrail_error"
            result.blocked = stage != "provider"
            result.text = "Request could not be completed safely. Please try again later."
        finally:
            result.latency_ms = (time.monotonic() - started) * 1000
        return result


def _make_pair(*, name, instruction, app_name, model, provider, client_kwargs,
               plugins=None, input_hooks=None, output_hooks=None, temperature=0.4):
    return (OpenAIAgent(name, instruction, provider),
            OpenAIRunner(app_name=app_name, model=model, provider=provider, client_kwargs=client_kwargs,
                         plugins=list(plugins or []), input_hooks=list(input_hooks or []),
                         output_hooks=list(output_hooks or []), temperature=temperature))


def create_blue_pair(*, name, instruction, app_name, plugins=None, input_hooks=None, output_hooks=None, temperature=0.4):
    return _make_pair(name=name, instruction=instruction, app_name=app_name,
                      model=get_blue_model(), provider=get_blue_provider(), client_kwargs=blue_client_kwargs(),
                      plugins=plugins, input_hooks=input_hooks, output_hooks=output_hooks, temperature=temperature)


def create_openai_pair(*, name, instruction, app_name, plugins=None, input_hooks=None, output_hooks=None, temperature=0.4, model=None):
    return _make_pair(name=name, instruction=instruction, app_name=app_name,
                      model=model or get_red_model(), provider=get_red_provider(), client_kwargs=red_openai_client_kwargs(),
                      plugins=plugins, input_hooks=input_hooks, output_hooks=output_hooks, temperature=temperature)
