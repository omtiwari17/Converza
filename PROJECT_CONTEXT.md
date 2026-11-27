# PROJECT_CONTEXT.md

## Project Purpose
Converza is a lightweight, private, self-hosted web file converter (video, audio, image, document, PDF) built with Flask and designed to run on Android via Termux. No accounts, no database, no Docker, no external cloud dependencies.

## Architecture Decisions
- **Strict module separation**:
  - `config.py`: paths (`uploads/`, `outputs/`), upload cap (`500 MB`), TTL (`3600s`), timeout (`900s`).
  - `registry.py`: sole owner of supported categories/targets, CLI tool detection, and `subprocess` argument-list builders (never `shell=True`).
  - `jobs.py`: sole owner of `subprocess` execution (`ThreadPoolExecutor(max_workers=1)`), thread-safe `JOBS` store, and TTL cleanup thread.
  - `app.py`: HTTP routing, upload/target validation, template/partial rendering.
- **No DB / No Redis**: In-memory job store (`JOBS`) protected by `threading.Lock`, single worker thread to prevent phone CPU thermal throttling.
- **Offline-first UI**: Vendored `htmx.min.js` + prebuilt Tailwind CSS 3 / DaisyUI 4 (`static/css/app.css`, compiled on PC).

## Tech Stack
- Python 3.11+, Flask 3.x, Waitress 3.x (`--threads=4`)
- Jinja2 + HTMX + Tailwind CSS 3 + DaisyUI 4 + inline Lucide SVGs
- CLI converters: `ffmpeg`, `magick`/`convert`, `pandoc`, `pdftoppm`/`pdftotext` (Poppler), `tesseract`

## File Structure
- `app.py` — Flask app factory (`create_app()`) and routes (`/`, `/healthz`)
- `config.py` — Constants and `ensure_dirs()`
- `templates/index.html` — Minimal skeleton page
- `requirements.txt` — `flask`, `waitress`
- `.gitignore` — Ignores `uploads/`, `outputs/`, `.venv/`, `__pycache__/`, `ui-build/node_modules/`
- `PROJECT_CONTEXT.md` — Persistent project state

## Completed Work
- **Phase 1 (Skeleton)**: Created project config, gitignore, requirements, Flask app factory with `/` and `/healthz`, minimal `templates/index.html`, and local `.venv` with `flask==3.1.3` and `waitress==3.0.2`. Verified via Flask `test_client` and live `waitress-serve` (`/` returns 200 with "Converza", `/healthz` returns `ok`).

## Current Work
- Phase 1 complete; ready for Phase 2 (`registry.py` and CLI conversion proof).

## Pending Tasks
- Phase 2: Implement `registry.py` + tool/policy detection + CLI verification
- Phase 3: Implement `jobs.py` + `/upload`, `/convert`, `/jobs`, `/download` + curl/HTTP verification
- Phase 4: Build Tailwind/DaisyUI CSS (`ui-build/`) + full templates & partials (`base.html`, `index.html`, `file_rows.html`, `job_row.html`) + vendor `htmx.min.js`
- Phase 5: Bulk `/convert-all`, `/zip`, multi-page PDF zipping, skipped-file notices, Retry
- Phase 6: Hardening & full Section 12 test suite
- Phase 7: Termux deployment verification

## Known Bugs / Environmental Notes
- On Windows dev machine: `python`, `node`, `npm`, `tesseract` are installed; `ffmpeg`, `magick`, `pandoc`, `pdftoppm` are not installed.
- Windows `C:\Windows\system32\convert.exe` shadows ImageMagick's `convert` name; `registry.py` must verify `-version` outputs `ImageMagick` before accepting `convert`.

## Important Implementation Details
- `app.py` exposes module-level `app = create_app()` so `waitress-serve ... app:app` works directly as specified in Section 10.
- Watch out for `werkzeug.utils.secure_filename` stripping non-ASCII stems (extract/validate extension before sanitizing display name; store files on disk strictly as `uploads/<uuid>/in.<ext>`).
