# PROJECT_CONTEXT.md

## Project Purpose
Converza is a lightweight, private, self-hosted web file converter (video, audio, image, document, PDF) built with Flask and designed to run on Android via Termux. No accounts, no database, no Docker, no external cloud dependencies.

## Architecture Decisions
- **Strict module separation**:
  - `config.py`: paths (`uploads/`, `outputs/`), upload cap (`500 MB`), TTL (`3600s`), timeout (`900s`).
  - `registry.py`: sole owner of supported categories/targets, CLI tool/policy detection, `pdftoppm` multi-page output collection, and `subprocess` argument-list builders (never `shell=True`).
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
- `registry.py` — Categories, targets, labels, cached tool/policy discovery (`get_tools`, `available_targets`), `build_cmd()`, `collect_multipage_outputs()`
- `tests/test_registry.py` — Registry unit tests + live CLI execution proofs (`tesseract`, `pdftotext`)
- `templates/index.html` — Minimal skeleton page
- `requirements.txt` — `flask`, `waitress`
- `.gitignore` — Ignores `uploads/`, `outputs/`, `.venv/`, `__pycache__/`, `ui-build/node_modules/`
- `PROJECT_CONTEXT.md` — Persistent project state

## Completed Work
- **Phase 1 (Skeleton)**: Created config, gitignore, requirements, Flask app factory (`/` and `/healthz`), minimal `templates/index.html`, and `.venv`. Verified via `test_client` and `waitress-serve`.
- **Phase 2 (Registry & CLI proof)**: Implemented `registry.py` with Windows `convert.exe` collision protection, ImageMagick PDF write policy probe, dynamic `available_targets()`, `build_cmd()`, and `collect_multipage_outputs()`. Added `tests/test_registry.py` (9/9 passing, including live `tesseract` and `pdftotext` CLI runs).

## Current Work
- Phase 2 complete; ready for Phase 3 (`jobs.py` and upload/convert/jobs/download routes).

## Pending Tasks
- Phase 3: Implement `jobs.py` + `/upload`, `/convert`, `/jobs`, `/download` + curl/HTTP verification
- Phase 4: Build Tailwind/DaisyUI CSS (`ui-build/`) + full templates & partials (`base.html`, `index.html`, `file_rows.html`, `job_row.html`) + vendor `htmx.min.js`
- Phase 5: Bulk `/convert-all`, `/zip`, multi-page PDF zipping, skipped-file notices, Retry
- Phase 6: Hardening & full Section 12 test suite
- Phase 7: Termux deployment verification

## Known Bugs / Environmental Notes
- On this Windows dev PC: `tesseract` and `pdftotext` (via Git mingw64) are installed and verified live; `ffmpeg`, `magick`, `pandoc`, and `pdftoppm` are not installed, so live CLI conversion for video/audio/magick-image/pandoc-doc/pdftoppm awaits either local PC installation or Termux deployment (Phase 7).
- Windows `C:\Windows\system32\convert.exe` is properly rejected by `_find_magick()` checking `-version` for `ImageMagick`.

## Important Implementation Details
- `app.py` exposes module-level `app = create_app()` so `waitress-serve ... app:app` works directly.
- `registry.is_multipage_target()` and `registry.collect_multipage_outputs()` encapsulate `pdftoppm` page-numbered output handling so `jobs.py` can zip multi-page renders cleanly in Phase 3/5.
- Watch out for `werkzeug.utils.secure_filename` stripping non-ASCII stems when building Phase 3 `/upload`.
