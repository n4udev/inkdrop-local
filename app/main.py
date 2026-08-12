from __future__ import annotations

import asyncio
import io
import multiprocessing
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from markitdown import MarkItDown

BASE_DIR = Path(__file__).resolve().parent
MAX_FILE_SIZE = 50 * 1024 * 1024
MAX_REQUEST_SIZE = MAX_FILE_SIZE + 1024 * 1024
PREVIEW_LIMIT = 1024 * 1024
MAX_MARKDOWN_SIZE = 20 * 1024 * 1024
CONVERSION_TIMEOUT = 120
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm", ".txt", ".md", ".csv", ".json", ".xml", ".jpg", ".jpeg", ".png"}
ORIGINS = {"http://127.0.0.1:8000", "http://localhost:8000"}
busy_guard = asyncio.Lock()
_busy = False

app = FastAPI(title="Inkdrop Local", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def convert_in_worker(input_path: str, extension: str, output_path: str, status_queue) -> None:
    """Run untrusted document parsing outside the web server process."""
    try:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (CONVERSION_TIMEOUT + 5, CONVERSION_TIMEOUT + 5))
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        except (ImportError, OSError, ValueError):
            pass
        with open(input_path, "rb") as stream:
            result = MarkItDown(enable_plugins=False).convert_stream(stream, file_extension=extension)
        markdown = result.text_content
        if not isinstance(markdown, str) or len(markdown) > MAX_MARKDOWN_SIZE:
            status_queue.put("output_too_large")
            return
        with open(output_path, "w", encoding="utf-8", newline="") as output:
            output.write(markdown)
        status_queue.put("ok")
    except Exception:
        status_queue.put("error")


def error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def apply_security_headers(response: JSONResponse) -> JSONResponse:
    response.headers.update({"Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})
    return response


def safe_filename(value: str | None) -> tuple[str | None, str | None]:
    if not value or "\x00" in value:
        return None, "invalid_filename"
    name = Path(value.replace("\\", "/")).name
    if not name or name in {".", ".."} or len(name) > 255:
        return None, "invalid_filename"
    return name, None


@app.middleware("http")
async def security(request: Request, call_next):
    host = request.headers.get("host", "")
    if host not in {"127.0.0.1:8000", "localhost:8000"}:
        return apply_security_headers(error("invalid_host", "Requests must use the local app address.", 403))
    origin = request.headers.get("origin")
    if request.url.path == "/api/convert" and request.method == "POST":
        if not origin or origin not in ORIGINS:
            return apply_security_headers(error("invalid_origin", "Requests must originate from the local app.", 403))
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > MAX_REQUEST_SIZE:
            return apply_security_headers(error("request_too_large", "The upload request is too large.", 413))
    elif origin and origin not in ORIGINS:
        return apply_security_headers(error("invalid_origin", "Requests must originate from the local app.", 403))
    response = await call_next(request)
    return apply_security_headers(response)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": "inkdrop-local", "version": "1.0.0"}


@app.post("/api/convert")
async def convert(file: UploadFile = File(...)) -> JSONResponse:
    global _busy
    filename, invalid = safe_filename(file.filename)
    if invalid:
        await file.close()
        return error(invalid, "The uploaded filename is invalid.", 400)
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        await file.close()
        return error("unsupported_type", "This file type is not supported.", 415)
    if _busy:
        await file.close()
        return error("conversion_busy", "Another conversion is already in progress.", 409)
    async with busy_guard:
        if _busy:
            await file.close()
            return error("conversion_busy", "Another conversion is already in progress.", 409)
        _busy = True
    stream = None
    input_path = None
    worker = None
    status_queue = None
    output_path = None
    try:
        named_stream = tempfile.NamedTemporaryFile(prefix="inkdrop-", suffix=".upload", delete=False)
        input_path = named_stream.name
        stream = io.BufferedRandom(named_stream)
        while chunk := await file.read(1024 * 1024):
            stream.write(chunk)
            if stream.tell() > MAX_FILE_SIZE:
                return error("file_too_large", "Files must be 50 MB or smaller.", 413)
        if not stream.tell():
            return error("empty_file", "The uploaded file is empty.", 400)
        try:
            stream.flush()
            stream.close()
            stream = None
            output_file = tempfile.NamedTemporaryFile(prefix="inkdrop-", suffix=".result", delete=False)
            output_path = output_file.name
            output_file.close()
            context = multiprocessing.get_context("spawn")
            status_queue = context.Queue(maxsize=1)
            worker = context.Process(target=convert_in_worker, args=(input_path, extension, output_path, status_queue), daemon=True)
            worker.start()
            await asyncio.to_thread(worker.join, CONVERSION_TIMEOUT)
            if worker.is_alive():
                worker.terminate()
                await asyncio.to_thread(worker.join, 5)
                return error("conversion_timeout", "The file took too long to convert.", 422)
            result_status = status_queue.get(timeout=1)
            if result_status == "output_too_large":
                return error("output_too_large", "The converted Markdown is too large to return.", 413)
            if result_status != "ok" or output_path is None:
                return error("conversion_failed", "The file could not be converted.", 422)
            if os.path.getsize(output_path) > MAX_MARKDOWN_SIZE * 4:
                return error("output_too_large", "The converted Markdown is too large to return.", 413)
            with open(output_path, encoding="utf-8") as output:
                markdown = output.read(MAX_MARKDOWN_SIZE + 1)
            if len(markdown) > MAX_MARKDOWN_SIZE:
                return error("output_too_large", "The converted Markdown is too large to return.", 413)
        except Exception:
            return error("conversion_failed", "The file could not be converted.", 422)
        return JSONResponse({"filename": filename, "outputFilename": f"{Path(filename).stem}.md", "markdown": markdown, "characters": len(markdown), "words": len(markdown.split()), "previewAvailable": len(markdown) <= PREVIEW_LIMIT})
    finally:
        _busy = False
        if worker is not None and worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)
        if status_queue is not None:
            status_queue.close()
        if stream is not None:
            stream.close()
        if input_path is not None:
            try:
                os.unlink(input_path)
            except FileNotFoundError:
                pass
        if output_path is not None:
            try:
                os.unlink(output_path)
            except FileNotFoundError:
                pass
        await file.close()
