import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRETARY_DATA_DIR", str(tmp_path))
    from app import llm, main

    async def fake_stream(messages, settings):
        for part in ["안녕", "하세요"]:
            yield part

    async def fake_complete(messages, settings):
        return '설명: {"tasks": [{"title": "디자인 회의", "due": "2026-11-02 15:00"}, {"title": "로그인 페이지", "due": "금요일"}]}'

    monkeypatch.setattr(llm, "stream_chat", fake_stream)
    monkeypatch.setattr(llm, "complete", fake_complete)
    with TestClient(main.app) as c:
        yield c


def test_chat_saves_history_and_title(client):
    conv = client.post("/api/conversations").json()
    res = client.post(f"/api/conversations/{conv['id']}/chat", json={"content": "웹페이지 구조 고민 중이야"})
    assert res.status_code == 200
    assert res.text == "안녕하세요"
    msgs = client.get(f"/api/conversations/{conv['id']}/messages").json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["content"] == "안녕하세요"
    assert client.get("/api/conversations").json()[0]["title"] == "웹페이지 구조 고민 중이야"


def test_chat_error_is_streamed(client, monkeypatch):
    from app import llm

    async def broken(messages, settings):
        raise llm.LLMError("연결 실패")
        yield  # noqa

    monkeypatch.setattr(llm, "stream_chat", broken)
    conv = client.post("/api/conversations").json()
    res = client.post(f"/api/conversations/{conv['id']}/chat", json={"content": "hi"})
    assert "[오류] 연결 실패" in res.text
    # 실패한 답변은 저장하지 않음
    assert len(client.get(f"/api/conversations/{conv['id']}/messages").json()) == 1


def test_settings_roundtrip(client):
    assert client.get("/api/settings").json()["model"] == "qwen2.5-coder:7b"
    out = client.put("/api/settings", json={"model": "exaone3.5:7.8b", "max_doc_chars": 5000}).json()
    assert out["model"] == "exaone3.5:7.8b"
    assert out["max_doc_chars"] == "5000"


def test_tasks_crud(client):
    t = client.post("/api/tasks", json={"title": "배포", "due": "2026-11-03"}).json()
    client.patch(f"/api/tasks/{t['id']}", json={"done": True})
    assert client.get("/api/tasks").json()[0]["done"] == 1
    client.delete(f"/api/tasks/{t['id']}")
    assert client.get("/api/tasks").json() == []


def test_tasks_parse_drops_bad_dates(client):
    created = client.post("/api/tasks/parse", json={"text": "내일 3시 회의, 금요일까지 로그인"}).json()["created"]
    assert [(t["title"], t["due"]) for t in created] == [
        ("디자인 회의", "2026-11-02 15:00"),
        ("로그인 페이지", None),
    ]


def test_document_extract_and_run(client):
    res = client.post("/api/documents/extract", files={"file": ("메모.txt", "회의 내용".encode("cp949"))})
    assert res.json()["text"] == "회의 내용"
    bad = client.post("/api/documents/extract", files={"file": ("a.png", b"x")})
    assert bad.status_code == 400
    run = client.post("/api/documents/run", json={"mode": "summary", "text": "회의 내용"})
    assert run.text == "안녕하세요"
