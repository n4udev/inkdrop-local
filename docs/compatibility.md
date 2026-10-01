# Inkdrop Local compatibility notes

Inkdrop Local uses Microsoft MarkItDown as a dependency and does not copy its converters. The lockfile now resolves MarkItDown 0.1.8, released September 21, 2026. The upgrade adopts the released fixes listed below; Inkdrop's regression suite checks the affected upload behavior before the dependency is advanced.

## Local conversion controls

The app writes each upload to a temporary local file and parses it in a separate worker process with MarkItDown plugins disabled. The parent process enforces a 120-second wall-clock timeout. On Unix, the worker also receives CPU, address-space, and open-file limits when the operating system exposes them. The worker writes converted Markdown to a temporary result file and caps it at 20 MB before the parent returns it. The app removes both files after success, failure, timeout, or oversized output.

## Adopted in MarkItDown 0.1.8

- [#2189](https://github.com/microsoft/markitdown/pull/2189): handles DOCX math runs with no text child. The related proposals [#2204](https://github.com/microsoft/markitdown/pull/2204) and [#2195](https://github.com/microsoft/markitdown/pull/2195) were closed as duplicates of this fix.
- [#2190](https://github.com/microsoft/markitdown/pull/2190): tolerates malformed DOCX styles that are missing a type.
- [#2194](https://github.com/microsoft/markitdown/pull/2194): preserves PPTX chart conversion when the chart title has no text frame.
- [#2418](https://github.com/microsoft/markitdown/pull/2418): avoids turning undecodable TXT/CSV input into the fabricated text `None`. The earlier [#2222](https://github.com/microsoft/markitdown/pull/2222) proposal was closed unmerged on September 30; #2418 merged on September 9 and is the fix included in 0.1.8. Inkdrop has TXT and CSV upload regression cases for this behavior.

## Still under review upstream

- [#2224](https://github.com/microsoft/markitdown/pull/2224): proposes preserving merged DOCX tables as semantic HTML. It remains open and is not included in 0.1.8.
- [#2215](https://github.com/microsoft/markitdown/pull/2215): proposes clarifying built-in PDF conversion limitations. It remains open; Inkdrop already documents the same limitation here and in the UI.

## Explicitly out of scope

These pull requests don't enable OCR, batch processing, MCP file-output features, remote URLs, plugins, or unrelated CLI and README changes. GIF support remains outside the current format list and requires a separate product decision.
