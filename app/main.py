"""AI 비서 웹 서버. `python -m app`으로 실행하면 브라우저가 열립니다."""

import json
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, documents, llm, prompts

STATIC_DIR = Path(__file__).parent / "static"
HISTORY_LIMIT = 20  # 모델에 함께 보낼 최근 대화 수
ERROR_MARK = "\n\n[오류] "
DUE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?$")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init()
    yield


app = FastAPI(title="AI 비서 (회사용)", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# ---------- 설정 ----------

class SettingsIn(BaseModel):
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    max_doc_chars: int | None = None


@app.get("/api/settings")
def get_settings() -> dict:
    return db.get_settings()


@app.put("/api/settings")
def put_settings(body: SettingsIn) -> dict:
    return db.update_settings(body.model_dump(exclude_none=True))


@app.get("/api/models")
async def models() -> dict:
    try:
        return {"models": await llm.list_models(db.get_settings())}
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc))


# ---------- 대화 ----------

class ChatIn(BaseModel):
    content: str


@app.get("/api/conversations")
def conversations() -> list[dict]:
    return db.list_conversations()


@app.post("/api/conversations")
def new_conversation() -> dict:
    return db.create_conversation()


@app.delete("/api/conversations/{conv_id}")
def remove_conversation(conv_id: int) -> dict:
    db.delete_conversation(conv_id)
    return {"ok": True}


@app.get("/api/conversations/{conv_id}/messages")
def messages(conv_id: int) -> list[dict]:
    return db.list_messages(conv_id)


def _stream(messages: list[dict], on_done=None) -> StreamingResponse:
    settings = db.get_settings()

    async def gen():
        parts: list[str] = []
        try:
            async for text in llm.stream_chat(messages, settings):
                parts.append(text)
                yield text
        except llm.LLMError as exc:
            yield ERROR_MARK + str(exc)
        finally:
            if on_done and parts:
                on_done("".join(parts))

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")


@app.post("/api/conversations/{conv_id}/chat")
def chat(conv_id: int, body: ChatIn) -> StreamingResponse:
    conv = db.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "대화를 찾을 수 없습니다.")
    content = body.content.strip()
    if not content:
        raise HTTPException(400, "내용을 입력해 주세요.")

    if not db.list_messages(conv_id):
        db.rename_conversation(conv_id, content[:30])
    db.add_message(conv_id, "user", content)

    history = db.list_messages(conv_id)[-HISTORY_LIMIT:]
    messages = [{"role": "system", "content": prompts.chat_system(db.list_tasks())}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]
    return _stream(messages, on_done=lambda text: db.add_message(conv_id, "assistant", text))


# ---------- 문서 ----------

class DocIn(BaseModel):
    mode: str = "summary"
    text: str
    instruction: str = ""


@app.post("/api/documents/extract")
async def extract(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    try:
        text = documents.extract_text(file.filename or "", data)
    except documents.UnsupportedFile as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:  # 손상된 PDF 등
        raise HTTPException(400, f"파일을 읽지 못했습니다: {exc}")
    if not text.strip():
        raise HTTPException(400, "파일에서 글자를 찾지 못했습니다. (스캔한 이미지 PDF는 지원하지 않습니다)")
    return {"filename": file.filename, "text": text}


@app.post("/api/documents/run")
def run_document(body: DocIn) -> StreamingResponse:
    if not body.text.strip():
        raise HTTPException(400, "문서 내용이 비어 있습니다.")
    limit = int(db.get_settings()["max_doc_chars"])
    text = body.text[:limit]
    return _stream(prompts.doc_prompt(body.mode, text, body.instruction))


# ---------- 할 일 ----------

class TaskIn(BaseModel):
    title: str
    due: str | None = None


class TaskPatch(BaseModel):
    title: str | None = None
    due: str | None = None
    done: bool | None = None


class ParseIn(BaseModel):
    text: str


@app.get("/api/tasks")
def tasks() -> list[dict]:
    return db.list_tasks()


@app.post("/api/tasks")
def add_task(body: TaskIn) -> dict:
    if not body.title.strip():
        raise HTTPException(400, "할 일을 입력해 주세요.")
    return db.create_task(body.title.strip(), body.due)


@app.patch("/api/tasks/{task_id}")
def edit_task(task_id: int, body: TaskPatch) -> dict:
    task = db.update_task(task_id, body.model_dump(exclude_unset=True))
    if not task:
        raise HTTPException(404, "할 일을 찾을 수 없습니다.")
    return task


@app.delete("/api/tasks/{task_id}")
def remove_task(task_id: int) -> dict:
    db.delete_task(task_id)
    return {"ok": True}


def parse_tasks_json(text: str) -> list[dict]:
    """모델 응답에서 JSON을 찾아 할 일 목록으로 바꿉니다. 형식이 이상하면 버립니다."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    result = []
    for item in data.get("tasks", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict) or not str(item.get("title", "")).strip():
            continue
        due = item.get("due")
        due = due.strip() if isinstance(due, str) and DUE_RE.match(due.strip()) else None
        result.append({"title": str(item["title"]).strip(), "due": due})
    return result


@app.post("/api/tasks/parse")
async def parse_tasks(body: ParseIn) -> dict:
    try:
        reply = await llm.complete(prompts.task_parse_prompt(body.text), db.get_settings())
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc))
    items = parse_tasks_json(reply)
    if not items:
        raise HTTPException(422, "할 일을 알아듣지 못했습니다. 조금 더 구체적으로 써 주세요.")
    return {"created": [db.create_task(i["title"], i["due"]) for i in items]}
