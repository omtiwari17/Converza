# PROJECT_CONTEXT.md

## Project Purpose
Converza is a lightweight, private, self-hosted web file converter (video, audio, image, document, PDF) built with Flask and designed to run on Android via Termux. No accounts, no database, no Docker, no external cloud dependencies.

## Architecture Decisions
- **Strict module separation**:
  - `config.py`: paths (`uploads/`, `outputs/`), upload cap (`500 MB`), TTL (`3600s`), timeout (`900s`).
  - `registry.py`: sole owner of supported categories/targets, CLI tool/policy detection, `pdftoppm` multi-page output collection, and `subprocess` argument-list builders (never `shell=True`).
  - `jobs.py`: sole owner of `subprocess` execution (`ThreadPoolExecutor(max_workers=1)`), thread-safe `JOBS` store, multi-page output zipping, bulk ZIP archive assembly, and TTL cleanup thread.
  - `app.py`: HTTP routing, upload/target validation, optional `CONVERZA_PASSWORD` Basic Auth gate, security headers, template/partial rendering.
- **No DB / No Redis**: In-memory job store (`JOBS`) protected by `threading.Lock`, single worker thread to prevent phone CPU thermal throttling.
- **Offline-first UI**: Vendored `htmx.min.js` + prebuilt Tailwind CSS 3 / DaisyUI 4 (`static/css/app.css`, compiled on PC).

## Tech Stack
- Python 3.11+, Flask 3.x, Waitress 3.x (`--threads=4`)
- Jinja2 + HTMX 2.0.4 (vendored) + Tailwind CSS 3 + DaisyUI 4 + inline Lucide SVGs
- CLI converters: `ffmpeg`, `magick`/`convert`, `pandoc`, `pdftoppm`/`pdftotext` (Poppler), `tesseract`

## File Structure
- `app.py` — Flask app factory (`create_app()`) and routes (`/`, `/healthz`, `/upload`, `/convert/<id>`, `/convert-all`, `/jobs/<id>`, `/download/<id>`, `/zip`, `413` error handler, optional auth gate, security headers)
- `config.py` — Constants and `ensure_dirs()`
- `registry.py` — Categories, targets, labels, cached tool/policy discovery (`get_tools`, `available_targets`), `build_cmd()`, `collect_multipage_outputs()`
- `jobs.py` — `is_valid_job_id()`, `create_job()`, `get_job()`, `delete_job()`, `submit()`, `run_job()`, `_finalize_output()`, `build_zip_archive()`, `cleanup_expired()`, `start_cleanup_thread()`, `clear_stale_dirs()`
- `templates/base.html` — Layout, `converza-dark`/`converza-light` theme toggle (`localStorage` + `<meta name="color-scheme">`), Known Limits footer
- `templates/index.html` — Dropzone card, drag-and-drop JS, `#upload-error` (with 413 handling), bulk bar (`>= 2` rows) wired to `/convert-all` and `/zip`, `#files` list, polite live region
- `templates/partials/file_rows.html` — Uploaded rows + skipped-file warning alert + empty notice
- `templates/partials/job_row.html` — Job card partial (`uploaded`, `queued`, `running`, `done`, `error` + Retry, OOB swap support)
- `templates/partials/convert_all.html` — Bulk response list of `job_row.html` partials
- `static/css/app.css` — Compiled minified Tailwind 3 + DaisyUI 4 CSS
- `static/js/htmx.min.js` — Vendored HTMX 2.0.4
- `ui-build/` — PC-only Tailwind/DaisyUI build config (`package.json`, `package-lock.json`, `tailwind.config.js`, `input.css`)
- `tests/` — `test_registry.py`, `test_routes.py`, `test_hardening.py`
- `requirements.txt` — `flask`, `waitress`
- `.gitignore` — Ignores `uploads/`, `outputs/`, `.venv/`, `__pycache__/`, `ui-build/node_modules/`
- `PROJECT_CONTEXT.md` — Persistent project state

## Completed Work
- **Phase 1 (Skeleton)**: Created config, gitignore, requirements, Flask app factory (`/` and `/healthz`), and `.venv`.
- **Phase 2 (Registry & CLI proof)**: Implemented `registry.py` with Windows `convert.exe` collision protection, ImageMagick PDF write policy probe, dynamic `available_targets()`, `build_cmd()`, and `collect_multipage_outputs()`.
- **Phase 3 (Jobs & routes)**: Implemented `jobs.py`, `/upload`, `/convert/<job_id>`, `/jobs/<job_id>`, `/download/<job_id>`, and verified via `unittest` + live `waitress-serve` + `curl.exe`.
- **Phase 4 (UI)**: Built `ui-build/` Tailwind 3 + DaisyUI 4 CSS (`static/css/app.css`), vendored `htmx.min.js` (`2.0.4`), and implemented `base.html`, `index.html`, and styled partials.
- **Phase 5 (Bulk & polish)**: Added `POST /convert-all`, `GET /zip?ids=...` (disk-backed streaming ZIP with cleanup), `413` error handler, Retry recovery, and 5-mixed-file tests.
- **Phase 6 (Hardening)**: Added strict 32-hex `is_valid_job_id()` + `OUTPUT_DIR` `is_relative_to()` path containment checks, `delete_job()` cleanup on failed upload write, `X-Content-Type-Options: nosniff` and `X-Frame-Options: SAMEORIGIN` headers, optional `CONVERZA_PASSWORD` HTTP Basic gate (leaving `/healthz` open), and `tests/test_hardening.py`. Verified **28 / 28** tests passing.

## Current Work
- Phase 6 complete; ready for Phase 7 (Termux deployment & 30-minute phone stability test).

## Pending Tasks
- Phase 7: Install packages in Termux, run `waitress-serve` inside `tmux` with `termux-wake-lock`, verify all 5 converter categories live on Android, and confirm 30-minute background stability.

## Known Bugs / Environmental Notes
- On Windows dev PC: `tesseract` and `pdftotext` ran live; `ffmpeg`, `magick`, `pandoc`, and `pdftoppm` are not installed on Windows (verified via AST/unit/mocked tests; live binary execution on Android awaits Phase 7 Termux deployment).
- Windows `C:\Windows\system32\convert.exe` is rejected by `_find_magick()`.

## Important Implementation Details
- `is_valid_job_id()` rejects any non-32-hex ID before `JOBS` lookup; `download()` and `build_zip_archive()` also assert `out_path.resolve().is_relative_to(OUTPUT_DIR.resolve())`.
- `CONVERZA_PASSWORD` environment variable enables Basic Auth (`hmac.compare_digest`) across all routes except `/healthz`; unset by default for local home Wi-Fi usage.
