"""OpenAI 호환 API 클라이언트.

Ollama, vLLM, LM Studio, 사내 LLM 서버 등 `/v1/chat/completions` 규격을
지원하는 서버라면 어디든 연결됩니다. (OpenAI 계정은 필요 없습니다.)
"""

import json
from collections.abc import AsyncIterator

import httpx

TIMEOUT = httpx.Timeout(connect=10.0, read=600.0, write=60.0, pool=10.0)


class LLMError(Exception):
    pass


def _headers(settings: dict) -> dict:
    headers = {"Content-Type": "application/json"}
    if settings.get("api_key"):
        headers["Authorization"] = f"Bearer {settings['api_key']}"
    return headers


def _url(settings: dict, path: str) -> str:
    return settings["base_url"].rstrip("/") + path


def _explain(exc: Exception, settings: dict) -> LLMError:
    if isinstance(exc, httpx.ConnectError):
        return LLMError(
            f"모델 서버({settings['base_url']})에 연결할 수 없습니다. "
            "Ollama가 실행 중인지 확인해 주세요."
        )
    if isinstance(exc, httpx.TimeoutException):
        return LLMError("모델 응답 시간이 초과되었습니다. 더 작은 모델을 쓰거나 입력을 줄여 보세요.")
    if isinstance(exc, httpx.HTTPStatusError):
        body = exc.response.text[:300]
        if exc.response.status_code == 404 and "model" in body.lower():
            return LLMError(
                f"모델 '{settings['model']}'을(를) 찾을 수 없습니다. "
                f"명령 프롬프트에서 `ollama pull {settings['model']}`을 실행해 주세요."
            )
        return LLMError(f"모델 서버 오류 ({exc.response.status_code}): {body}")
    return LLMError(str(exc))


async def stream_chat(messages: list[dict], settings: dict) -> AsyncIterator[str]:
    payload = {"model": settings["model"], "messages": messages, "stream": True}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            async with client.stream(
                "POST", _url(settings, "/chat/completions"), headers=_headers(settings), json=payload
            ) as resp:
                if resp.status_code >= 400:
                    await resp.aread()
                    resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if choices:
                        text = (choices[0].get("delta") or {}).get("content")
                        if text:
                            yield text
    except httpx.HTTPError as exc:
        raise _explain(exc, settings) from exc


async def complete(messages: list[dict], settings: dict) -> str:
    payload = {"model": settings["model"], "messages": messages, "stream": False}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                _url(settings, "/chat/completions"), headers=_headers(settings), json=payload
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"] or ""
    except httpx.HTTPError as exc:
        raise _explain(exc, settings) from exc


async def list_models(settings: dict) -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.get(_url(settings, "/models"), headers=_headers(settings))
            resp.raise_for_status()
            return sorted(m["id"] for m in resp.json().get("data", []))
    except httpx.HTTPError as exc:
        raise _explain(exc, settings) from exc
