# PROJECT_CONTEXT.md

## Project Purpose
Converza is a lightweight, private, self-hosted web file converter (video, audio, image, document, PDF) built with Flask and designed to run on Android via Termux. No accounts, no database, no Docker, no external cloud dependencies.

## Architecture Decisions
- **Strict module separation**:
  - `config.py`: paths (`uploads/`, `outputs/`), upload cap (`500 MB`), TTL (`3600s`), timeout (`900s`).
  - `registry.py`: sole owner of supported categories/targets, CLI tool/policy detection, `pdftoppm` multi-page output collection, and `subprocess` argument-list builders (never `shell=True`).
  - `jobs.py`: sole owner of `subprocess` execution (`ThreadPoolExecutor(max_workers=1)`), thread-safe `JOBS` store, multi-page output zipping, and TTL cleanup thread.
  - `app.py`: HTTP routing, upload/target validation, template/partial rendering.
- **No DB / No Redis**: In-memory job store (`JOBS`) protected by `threading.Lock`, single worker thread to prevent phone CPU thermal throttling.
- **Offline-first UI**: Vendored `htmx.min.js` + prebuilt Tailwind CSS 3 / DaisyUI 4 (`static/css/app.css`, compiled on PC).

## Tech Stack
- Python 3.11+, Flask 3.x, Waitress 3.x (`--threads=4`)
- Jinja2 + HTMX + Tailwind CSS 3 + DaisyUI 4 + inline Lucide SVGs
- CLI converters: `ffmpeg`, `magick`/`convert`, `pandoc`, `pdftoppm`/`pdftotext` (Poppler), `tesseract`

## File Structure
- `app.py` — Flask app factory (`create_app()`) and routes (`/`, `/healthz`, `/upload`, `/convert/<id>`, `/jobs/<id>`, `/download/<id>`)
- `config.py` — Constants and `ensure_dirs()`
- `registry.py` — Categories, targets, labels, cached tool/policy discovery (`get_tools`, `available_targets`), `build_cmd()`, `collect_multipage_outputs()`
- `jobs.py` — `create_job()`, `get_job()`, `submit()`, `run_job()`, `_finalize_output()`, `cleanup_expired()`, `start_cleanup_thread()`, `clear_stale_dirs()`
- `templates/index.html` — Minimal skeleton page (to be replaced in Phase 4)
- `templates/partials/file_rows.html` — Uploaded rows + skipped-file notice partial
- `templates/partials/job_row.html` — Job state partial (`uploaded`, `queued`, `running`, `done`, `error` + Retry)
- `tests/test_registry.py` — Registry unit tests + live CLI execution proofs
- `tests/test_routes.py` — Route/worker integration tests (upload, Unicode/traversal, convert, poll, download, errors, multipage zip, TTL cleanup)
- `requirements.txt` — `flask`, `waitress`
- `.gitignore` — Ignores `uploads/`, `outputs/`, `.venv/`, `__pycache__/`, `ui-build/node_modules/`
- `PROJECT_CONTEXT.md` — Persistent project state

## Completed Work
- **Phase 1 (Skeleton)**: Created config, gitignore, requirements, Flask app factory (`/` and `/healthz`), minimal `templates/index.html`, and `.venv`.
- **Phase 2 (Registry & CLI proof)**: Implemented `registry.py` with Windows `convert.exe` collision protection, ImageMagick PDF write policy probe, dynamic `available_targets()`, `build_cmd()`, and `collect_multipage_outputs()`.
- **Phase 3 (Jobs & routes)**: Implemented `jobs.py`, `/upload`, `/convert/<job_id>`, `/jobs/<job_id>`, `/download/<job_id>`, and functional partials. Verified 15/15 unit+integration tests and live `waitress-serve` + `curl.exe` end-to-end (`upload` → `convert` → `jobs` poll → `download`).

## Current Work
- Phase 3 complete; ready for Phase 4 (full mobile-first UI with Tailwind CSS 3 + DaisyUI 4 + vendored HTMX).

## Pending Tasks
- Phase 4: Build Tailwind/DaisyUI CSS (`ui-build/`) + full templates & partials (`base.html`, `index.html`, `file_rows.html`, `job_row.html`) + vendor `htmx.min.js`
- Phase 5: Bulk `/convert-all`, `/zip`, skipped-file & 413 polish, Retry UX polish
- Phase 6: Hardening & full Section 12 test suite
- Phase 7: Termux deployment verification

## Known Bugs / Environmental Notes
- On this Windows dev PC: `tesseract` and `pdftotext` (via Git mingw64) are installed and verified live; `ffmpeg`, `magick`, `pandoc`, and `pdftoppm` are not installed.
- Windows `C:\Windows\system32\convert.exe` is rejected by `_find_magick()`.

## Important Implementation Details
- `_parse_upload_name()` preserves Unicode/spaces for display and extracts `ext` before `secure_filename`, while saving strictly to `uploads/<uuid>/in.<ext>` and sanitizing `download_name` via `secure_filename(stem) or 'converted'`.
- `jobs.submit()` clears any prior `outputs/<job_id>` directory on retry and snapshots job dicts under `LOCK` for Waitress thread safety.
- `clear_stale_dirs()` cleans orphaned `uploads/` and `outputs/` subdirectories on startup.
