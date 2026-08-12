# Inkdrop Local compatibility notes

Inkdrop Local uses Microsoft MarkItDown as a dependency. It doesn't copy MarkItDown's converters. When an upstream fix is released, upgrade the pinned dependency and rerun the relevant tests before you adopt it.

## Local conversion controls

The app writes each upload to a temporary local file and parses it in a separate worker process with MarkItDown plugins disabled. The parent process enforces a 120-second wall-clock timeout. On Unix, the worker also receives CPU, address-space, and open-file limits when the operating system exposes them. The worker writes converted Markdown to a temporary result file and caps it at 20 MB before the parent returns it. The app removes both files after success, failure, timeout, or oversized output.

## Relevant upstream work

- [#2224](https://github.com/microsoft/markitdown/pull/2224): preserves merged DOCX tables as semantic HTML. Adopt it after release and retain a merged-cell DOCX regression fixture.
- [#2222](https://github.com/microsoft/markitdown/pull/2222): avoids literal `None` output when text or CSV charset detection fails. Adopt it after release and add TXT/CSV regression coverage.
- [#2204](https://github.com/microsoft/markitdown/pull/2204), [#2195](https://github.com/microsoft/markitdown/pull/2195), and [#2189](https://github.com/microsoft/markitdown/pull/2189): harden DOCX math conversion against empty or malformed runs.
- [#2194](https://github.com/microsoft/markitdown/pull/2194): avoid PPTX chart-title crashes when a chart lacks a text frame.
- [#2190](https://github.com/microsoft/markitdown/pull/2190): tolerate malformed DOCX styles.
- [#2215](https://github.com/microsoft/markitdown/pull/2215): clarifies PDF conversion limitations. The app documents the same limitation here and in the UI.

## Explicitly out of scope

These pull requests don't enable OCR, batch processing, MCP file-output features, remote URLs, plugins, or unrelated CLI and README changes. GIF support remains outside the current format list and requires a separate product decision.
