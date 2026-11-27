# PROJECT_CONTEXT.md

## Project Purpose
Converza is a lightweight, private, self-hosted web file converter (video, audio, image, document, PDF) built with Flask and designed to run on Android via Termux. No accounts, no database, no Docker, no external cloud dependencies.

## Architecture Decisions
- **Strict module separation**:
  - `config.py`: paths (`uploads/`, `outputs/`), upload cap (`500 MB`), TTL (`3600s`), timeout (`900s`).
  - `registry.py`: sole owner of supported categories/targets, CLI tool/policy detection, `pdftoppm` multi-page output collection, and `subprocess` argument-list builders (never `shell=True`).
  - `jobs.py`: sole owner of `subprocess` execution (`ThreadPoolExecutor(max_workers=1)`), thread-safe `JOBS` store, multi-page output zipping, bulk ZIP archive assembly, and TTL cleanup thread.
  - `app.py`: HTTP routing, upload/target validation, template/partial rendering.
- **No DB / No Redis**: In-memory job store (`JOBS`) protected by `threading.Lock`, single worker thread to prevent phone CPU thermal throttling.
- **Offline-first UI**: Vendored `htmx.min.js` + prebuilt Tailwind CSS 3 / DaisyUI 4 (`static/css/app.css`, compiled on PC).

## Tech Stack
- Python 3.11+, Flask 3.x, Waitress 3.x (`--threads=4`)
- Jinja2 + HTMX 2.0.4 (vendored) + Tailwind CSS 3 + DaisyUI 4 + inline Lucide SVGs
- CLI converters: `ffmpeg`, `magick`/`convert`, `pandoc`, `pdftoppm`/`pdftotext` (Poppler), `tesseract`

## File Structure
- `app.py` — Flask app factory (`create_app()`) and routes (`/`, `/healthz`, `/upload`, `/convert/<id>`, `/convert-all`, `/jobs/<id>`, `/download/<id>`, `/zip`, `413` error handler)
- `config.py` — Constants and `ensure_dirs()`
- `registry.py` — Categories, targets, labels, cached tool/policy discovery (`get_tools`, `available_targets`), `build_cmd()`, `collect_multipage_outputs()`
- `jobs.py` — `create_job()`, `get_job()`, `submit()`, `run_job()`, `_finalize_output()`, `build_zip_archive()`, `cleanup_expired()`, `start_cleanup_thread()`, `clear_stale_dirs()`
- `templates/base.html` — Layout, `converza-dark`/`converza-light` theme toggle (`localStorage` + `<meta name="color-scheme">`), Known Limits footer
- `templates/index.html` — Dropzone card, drag-and-drop JS, `#upload-error` (with 413 handling), bulk bar (`>= 2` rows) wired to `/convert-all` and `/zip`, `#files` list, polite live region
- `templates/partials/file_rows.html` — Uploaded rows + skipped-file warning alert + empty notice
- `templates/partials/job_row.html` — Job card partial (`uploaded`, `queued`, `running`, `done`, `error` + Retry, OOB swap support)
- `templates/partials/convert_all.html` — Bulk response list of `job_row.html` partials
- `static/css/app.css` — Compiled minified Tailwind 3 + DaisyUI 4 CSS
- `static/js/htmx.min.js` — Vendored HTMX 2.0.4
- `ui-build/` — PC-only Tailwind/DaisyUI build config (`package.json`, `package-lock.json`, `tailwind.config.js`, `input.css`)
- `tests/` — `test_registry.py`, `test_routes.py`
- `requirements.txt` — `flask`, `waitress`
- `.gitignore` — Ignores `uploads/`, `outputs/`, `.venv/`, `__pycache__/`, `ui-build/node_modules/`
- `PROJECT_CONTEXT.md` — Persistent project state

## Completed Work
- **Phase 1 (Skeleton)**: Created config, gitignore, requirements, Flask app factory (`/` and `/healthz`), and `.venv`.
- **Phase 2 (Registry & CLI proof)**: Implemented `registry.py` with Windows `convert.exe` collision protection, ImageMagick PDF write policy probe, dynamic `available_targets()`, `build_cmd()`, and `collect_multipage_outputs()`.
- **Phase 3 (Jobs & routes)**: Implemented `jobs.py`, `/upload`, `/convert/<job_id>`, `/jobs/<job_id>`, `/download/<job_id>`, and verified via `unittest` + live `waitress-serve` + `curl.exe`.
- **Phase 4 (UI)**: Built `ui-build/` Tailwind 3 + DaisyUI 4 CSS (`static/css/app.css`), vendored `htmx.min.js` (`2.0.4`), and implemented `base.html`, `index.html`, and styled partials.
- **Phase 5 (Bulk & polish)**: Added `POST /convert-all` (with HTMX OOB swaps for browser and HTML list for `curl`), `GET /zip?ids=...` (disk-backed temp ZIP with collision deduplication), `413` error handler + HTMX `beforeSwap` display, Retry recovery test, and 5-mixed-file convert-all + ZIP test (`20/20` unit tests passing + live Waitress `curl.exe` bulk+ZIP verified).

## Current Work
- Phase 5 complete; ready for Phase 6 (Hardening & full Section 12 test audit).

## Pending Tasks
- Phase 6: Security & hardening audit (Section 8.6 + full Section 12 test suite)
- Phase 7: Termux deployment verification

## Known Bugs / Environmental Notes
- On this Windows dev PC: `tesseract` and `pdftotext` (via Git mingw64) are installed and verified live; `ffmpeg`, `magick`, `pandoc`, and `pdftoppm` are not installed.
- Windows `C:\Windows\system32\convert.exe` is rejected by `_find_magick()`.

## Important Implementation Details
- `POST /convert-all` accepts `target_<job_id>` fields (and `job_id`/`target` pairs), validates every target before queueing, and sets `oob=True` when `HX-Request: true` so `#files` cards update individually in-place.
- `GET /zip?ids=...` deduplicates colliding archive entry names (`stem_2.ext`) and streams in 64 KB chunks from a temp file on disk (deleting via `finally` after the file handle closes) rather than buffering in memory.
