# Inkdrop Local

Inkdrop Local is a private browser interface powered by [Microsoft MarkItDown](https://github.com/microsoft/markitdown). It uploads files only to a server on your machine, converts them in temporary local storage, and returns Markdown.

## Install and run

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then clone the repository and install the locked dependencies:

```bash
git clone https://github.com/n4udev/inkdrop-local.git
cd inkdrop-local
uv sync --locked
```

`uv` installs the required Python 3.12 runtime when needed.

### macOS

Open Terminal and run:

```bash
./run.command
```

### Linux

Open a terminal in the repository and run:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

### Windows

Open PowerShell in the repository and run:

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Inkdrop Local opens at <http://127.0.0.1:8000> and stays accessible only from
your computer. Keep the terminal open while you use it; press `Control-C` to
stop the app. On macOS, `run.command` also checks the health endpoint and detects
port conflicts during startup.

## Test it

```bash
uv run pytest
```

The app accepts files up to 50 MB. It disables MarkItDown plugins and URL conversion and accepts only the supported extensions. It removes temporary data after each request.

## Release v1.0.0

This release runs locally and doesn't include accounts, a database, history, batch processing, remote URLs, OCR, cloud services, or native `.app` packaging. Before you commit, run the verification commands below and make sure generated folders such as `.venv/`, `__pycache__/`, and `.pytest_cache/` aren't staged.

## Security and scope

Uvicorn binds to `127.0.0.1`. The server rejects unexpected Host and Origin headers, enforces the 50 MB upload limit while it reads the file, and closes temporary upload data in a `finally` block. A separate worker process converts each file with plugins disabled. The parent enforces a wall-clock timeout, and the worker applies OS-level limits where the platform supports them. The app caps returned Markdown at 20 MB and removes temporary input and result files after every request. The launcher reuses a healthy local instance, detects port conflicts, waits for the health endpoint, and forwards termination signals.

The browser UI makes no CDN requests. It sanitizes Markdown immediately before inserting the preview and opens external links with `noopener noreferrer`. PDF conversion extracts available text and structure; scanned or image-only PDFs might produce little or no text because Inkdrop doesn't run OCR. Audio, ZIP, EPUB, Outlook, legacy `.xls`, remote URLs, and plugins aren't supported.

See [docs/compatibility.md](docs/compatibility.md) for the upstream MarkItDown changes being tracked for future dependency updates.

## License

Inkdrop Local's original code is available under the [MIT License](LICENSE).
Bundled third-party components retain their own licenses; see
[`app/static/vendor/NOTICE.txt`](app/static/vendor/NOTICE.txt) and the license
files in [`app/static/vendor/licenses/`](app/static/vendor/licenses/).

## Verification

The automated suite covers health identity, text conversion, unsupported types,
invalid Host and Origin, request and stream size limits, empty files, filename
normalization, conversion timeouts, cleanup, and safe error redaction.

```bash
node --check app/static/app.js
zsh -n run.command
uv run pytest
```
