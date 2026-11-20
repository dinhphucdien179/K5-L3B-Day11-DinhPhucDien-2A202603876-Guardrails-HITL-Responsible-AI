"""Shared chat adapter; explicit session ownership on both runtimes."""
from core.openai_runtime import OpenAIRunner


async def chat_with_agent(agent, runner, user_message: str, session_id=None, *, user_id="student", request_id=None):
    if isinstance(runner, OpenAIRunner):
        result = await runner.chat_detailed(agent, user_message, user_id=user_id, request_id=request_id, session_id=session_id)
        if result.error:
            raise RuntimeError(result.error)
        return result.text, result.session

    from google.genai import types
    sid = getattr(session_id, "id", session_id)
    session = None
    if sid:
        session = await runner.session_service.get_session(app_name=runner.app_name, user_id=user_id, session_id=sid)
    if session is None:
        session = await runner.session_service.create_session(app_name=runner.app_name, user_id=user_id)
    content = types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
    texts = []
    async for event in runner.run_async(user_id=user_id, session_id=session.id, new_message=content):
        error = getattr(event, "error_code", None)
        if error:
            raise RuntimeError(f"Model event error: {error}")
        body = getattr(event, "content", None)
        # Thought parts are never customer-visible output/evidence.
        if body and body.parts:
            texts.extend(p.text for p in body.parts if getattr(p, "text", None) and not getattr(p, "thought", False))
    text = "".join(texts)
    if not text:
        raise ValueError("Empty model response")
    return text, session
