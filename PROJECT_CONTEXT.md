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
- Jinja2 + HTMX 2.0.4 (vendored) + Tailwind CSS 3 + DaisyUI 4 + inline Lucide SVGs
- CLI converters: `ffmpeg`, `magick`/`convert`, `pandoc`, `pdftoppm`/`pdftotext` (Poppler), `tesseract`

## File Structure
- `app.py` — Flask app factory (`create_app()`) and routes (`/`, `/healthz`, `/upload`, `/convert/<id>`, `/jobs/<id>`, `/download/<id>`)
- `config.py` — Constants and `ensure_dirs()`
- `registry.py` — Categories, targets, labels, cached tool/policy discovery (`get_tools`, `available_targets`), `build_cmd()`, `collect_multipage_outputs()`
- `jobs.py` — `create_job()`, `get_job()`, `submit()`, `run_job()`, `_finalize_output()`, `cleanup_expired()`, `start_cleanup_thread()`, `clear_stale_dirs()`
- `templates/base.html` — Layout, `converza-dark`/`converza-light` theme toggle (`localStorage` + `<meta name="color-scheme">`), Known Limits footer
- `templates/index.html` — Dropzone card, drag-and-drop JS, bulk bar (`>= 2` rows), `#files` list, polite live region
- `templates/partials/file_rows.html` — Uploaded rows + skipped-file warning alert
- `templates/partials/job_row.html` — Job card partial (`uploaded`, `queued`, `running`, `done`, `error` + Retry) with inline Lucide category/action SVGs
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
- **Phase 4 (UI)**: Built `ui-build/` Tailwind 3 + DaisyUI 4 CSS (`static/css/app.css`), vendored `htmx.min.js` (`2.0.4`), and implemented `base.html`, `index.html`, and styled partials (`converza-dark` default + `converza-light` toggle, `44px` touch targets, inline Lucide SVGs, Known Limits footer). Verified `16/16` tests passing.

## Current Work
- Phase 4 complete; ready for Phase 5 (`POST /convert-all`, `GET /zip?ids=...`, error/413 polish).

## Pending Tasks
- Phase 5: Implement backend `/convert-all` & `/zip`, wire bulk bar directly to backend endpoints, polish 413/empty/error UX
- Phase 6: Hardening & full Section 12 test suite
- Phase 7: Termux deployment verification

## Known Bugs / Environmental Notes
- On this Windows dev PC: `tesseract` and `pdftotext` (via Git mingw64) are installed and verified live; `ffmpeg`, `magick`, `pandoc`, and `pdftoppm` are not installed.
- Windows `C:\Windows\system32\convert.exe` is rejected by `_find_magick()`.

## Important Implementation Details
- `ui-build/node_modules/` is git-ignored; `static/css/app.css` and `static/js/htmx.min.js` are committed so Termux never needs Node or CDN access.
- `base.html` sets `<meta name="color-scheme" content="dark">` with inline FOUC-prevention script (`try/catch` around `localStorage`) and CSS `:root:has(> head > meta[name="color-scheme"][content="light|dark"])` mapping.
- `input.css` disables non-progress animations per Section 9 and slows indeterminate progress animation under `prefers-reduced-motion: reduce` instead of `animation: none`.
