import io

from fastapi.testclient import TestClient
import pytest
from markitdown import MarkItDown

from app.main import app

client = TestClient(app)
LOCAL_HEADERS = {"host": "127.0.0.1:8000"}
CONVERT_HEADERS = {**LOCAL_HEADERS, "origin": "http://127.0.0.1:8000"}


def test_home_page():
    response = client.get("/", headers=LOCAL_HEADERS)
    assert response.status_code == 200
    assert "Inkdrop Local" in response.text


def test_health():
    assert client.get("/api/health", headers=LOCAL_HEADERS).json() == {"status": "ok", "app": "inkdrop-local", "version": "1.0.0"}


def test_text_conversion():
    response = client.post(
        "/api/convert",
        headers=CONVERT_HEADERS, files={"file": ("notes.txt", b"Hello from MarkItDown", "text/plain")},
    )
    assert response.status_code == 200
    assert "Hello from MarkItDown" in response.json()["markdown"]


def test_csv_conversion_returns_markdown():
    response = client.post(
        "/api/convert",
        headers=CONVERT_HEADERS,
        files={"file": ("contacts.csv", b"name,role\nAda,Engineer\n", "text/csv")},
    )
    assert response.status_code == 200
    assert "Ada" in response.json()["markdown"]


def test_undecodable_text_and_csv_do_not_become_literal_none():
    converter = MarkItDown(enable_plugins=False)
    data = b"\xff\xfe\xff\xff\x00"

    text = converter.convert_stream(io.BytesIO(data), file_extension=".txt").text_content
    csv = converter.convert_stream(io.BytesIO(data), file_extension=".csv").text_content

    assert text != "None"
    assert csv != "| None |\n| --- |"


def test_html_conversion_returns_content():
    response = client.post(
        "/api/convert",
        headers=CONVERT_HEADERS,
        files={"file": ("note.html", b"<h1>Example</h1><p>Local content</p>", "text/html")},
    )
    assert response.status_code == 200
    assert "Example" in response.json()["markdown"]


def test_rejects_unknown_extension():
    response = client.post(
        "/api/convert",
        headers=CONVERT_HEADERS, files={"file": ("payload.exe", b"nope", "application/octet-stream")},
    )
    assert response.status_code == 415


def test_rejects_invalid_host_and_origin():
    host_error = client.get("/api/health", headers={"host": "example.test"})
    assert host_error.status_code == 403
    origin_error = client.get("/api/health", headers={**LOCAL_HEADERS, "origin": "https://example.test"})
    assert origin_error.status_code == 403
    for response in (host_error, origin_error):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["cache-control"] == "no-store"


def test_post_rejects_missing_origin():
    response = client.post(
        "/api/convert",
        headers=LOCAL_HEADERS, files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "invalid_origin"


def test_rejects_oversized_request_before_multipart_parse():
    response = client.post(
        "/api/convert",
        headers={**CONVERT_HEADERS, "content-length": str(52 * 1024 * 1024)},
        content=b"not parsed",
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


def test_busy_lock_returns_409(monkeypatch):
    monkeypatch.setattr("app.main._busy", True)
    response = client.post("/api/convert", headers=CONVERT_HEADERS, files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conversion_busy"


def test_empty_file_and_path_traversal_are_safe():
    empty = client.post("/api/convert", headers=CONVERT_HEADERS, files={"file": ("empty.txt", b"", "text/plain")})
    assert empty.status_code == 400
    assert empty.json()["error"]["code"] == "empty_file"
    traversal = client.post("/api/convert", headers=CONVERT_HEADERS, files={"file": ("../../passwd.txt", b"safe", "text/plain")})
    assert traversal.status_code == 200
    assert traversal.json()["filename"] == "passwd.txt"


def test_rejects_oversized_stream():
    response = client.post("/api/convert", headers=CONVERT_HEADERS, files={"file": ("large.txt", b"x" * (50 * 1024 * 1024 + 1), "text/plain")})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_conversion_exception_returns_safe_error(monkeypatch):
    monkeypatch.setattr("app.main.convert_in_worker", lambda *_args: (_ for _ in ()).throw(RuntimeError("private path should not leak")))
    response = client.post("/api/convert", headers=CONVERT_HEADERS, files={"file": ("broken.pdf", b"not a pdf", "application/pdf")})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "conversion_failed"
    assert "private path" not in response.text


def test_conversion_timeout_returns_safe_error(monkeypatch):
    class FakeQueue:
        def close(self): pass

    class FakeProcess:
        def __init__(self, *_args, **_kwargs): self.terminated = False
        def start(self): pass
        def join(self, *_args): pass
        def is_alive(self): return not self.terminated
        def terminate(self): self.terminated = True

    class FakeContext:
        Queue = lambda *_args, **_kwargs: FakeQueue()
        Process = FakeProcess

    monkeypatch.setattr("app.main.multiprocessing.get_context", lambda *_args: FakeContext())
    monkeypatch.setattr("app.main.CONVERSION_TIMEOUT", 0.001)
    response = client.post("/api/convert", headers=CONVERT_HEADERS, files={"file": ("slow.txt", b"hello", "text/plain")})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "conversion_timeout"


def test_frontend_keeps_sanitization_at_dom_boundary():
    script = open("app/static/app.js", encoding="utf-8").read()
    assert "DOMPurify.sanitize(marked.parse" in script
    assert "FORBID_TAGS" in script
    assert "noopener noreferrer" in script
    uri_policy = script.split("ALLOWED_URI_REGEXP:", 1)[1].split("})", 1)[0]
    assert "javascript:" not in uri_policy
    assert "data:" not in uri_policy
    assert "file:" not in uri_policy
