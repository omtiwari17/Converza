# PROJECT_CONTEXT.md

## Project Purpose
Converza is a lightweight, private, self-hosted web file converter (video, audio, image, document, PDF) built with Flask and designed to run on Android via Termux. No accounts, no database, no Docker, no external cloud dependencies.

## Architecture Decisions
- **Strict module separation**:
  - `config.py`: paths (`uploads/`, `outputs/`), upload cap (`500 MB`), TTL (`3600s`), timeout (`900s`).
  - `registry.py`: sole owner of supported categories/targets, default target selection (`default_target()`), engine status checks (`engine_statuses()`, `all_engines_ready()`), whitelisted per-card options (`validate_options()`), `pdftoppm` multi-page output collection, and `subprocess` argument-list builders (never `shell=True`).
  - `jobs.py`: sole owner of `subprocess` execution (`ThreadPoolExecutor(max_workers=1)` via `Popen`), thread-safe `JOBS` store, elapsed/output-size tracking, reset (`reset_job()`), multi-page output zipping, bulk ZIP archive assembly, and TTL cleanup thread.
  - `app.py`: HTTP routing, upload/target/option validation, optional `CONVERZA_PASSWORD` Basic Auth gate, security headers, HTMX OOB partial rendering.
- **No DB / No Redis**: In-memory job store (`JOBS`) protected by `threading.Lock`, single worker thread to prevent phone CPU thermal throttling.
- **Mobile-first UI (`CONVERZA_UI_SPEC.md`)**: Single `640px` centered column, DaisyUI `converza-dark`/`converza-light` themes (`localStorage.theme`), vendored `htmx.min.js`, prebuilt `static/css/app.css` (< 100 KB), and inline Lucide SVGs in `_icons.html`.

## Tech Stack
- Python 3.11+, Flask 3.x, Waitress 3.x (`--threads=4`)
- Jinja2 + HTMX 2.0.4 (vendored) + Tailwind CSS 3 + DaisyUI 4 + inline Lucide SVG macros
- CLI converters: `ffmpeg`, `magick`/`convert`, `pandoc`, `pdftoppm`/`pdftotext`/`pdftohtml` (Poppler), `tesseract`

## File Structure
- `app.py` — Flask app factory (`create_app()`) and routes (`/`, `/info`, `/healthz`, `/upload`, `/convert/<id>`, `/convert-all`, `/jobs/<id>` GET/DELETE, `/jobs/<id>/delete`, `/jobs/<id>/cancel`, `/jobs/<id>/reset`, `/jobs/<id>/text`, `/jobs/<id>/preview`, `/jobs/<id>/media`, `/download/<id>`, `/download/<id>/page/<n>`, `/zip`, `413` toast handler)
- `config.py` — Constants and `ensure_dirs()`
- `registry.py` — Categories, targets, labels, smart default targets, engine status checks, cached tool/policy/`ocr_langs` discovery, `validate_options()`, `build_cmd()`, `build_steps()`, `collect_multipage_outputs()`
- `jobs.py` — `is_valid_job_id()`, `create_job()`, `get_job()`, `list_jobs()`, `delete_job()`, `reset_job()`, `cancel_job()`, `submit()`, `run_job()`, `_finalize_output()`, `get_job_page_path()`, `build_zip_archive()`, `cleanup_expired()`, `start_cleanup_thread()`, `clear_stale_dirs()`
- `templates/_icons.html` — 16 inline Lucide SVG icon macros
- `templates/base.html` — Sticky 56px header (logo, status dot, icon-only theme toggle), `<main>` (`max-w-[640px]`), `#toast-area`, Info bottom sheet `<dialog>`, lightbox `<dialog id="preview-modal">`
- `templates/index.html` — Intro (empty only), empty/slim dropzone (`Add more files` when files exist), drag-over & mouse-only `Ctrl+V` paste, `#file-list`, footer line, `#bulk-bar`
- `templates/partials/file_card.html` — Unified file card (category chip, middle-preserving filename, radio format chips, per-card collapsible Options, 5 state actions + `Pages (N)` / `Preview` options)
- `templates/partials/bulk_bar.html` — Fixed bottom bar (`Convert all (N)` / `Converting N of M...` / `Download all (ZIP)`) with OOB swaps
- `templates/partials/info.html` — Info bottom sheet content (Engines, accordion Supported formats, Known limits)
- `templates/partials/toast.html` — Auto-dismissing DaisyUI toast alert
- `templates/partials/upload_response.html` & `convert_all.html` — Multi-card + OOB bulk bar/toast responses
- `templates/partials/pages_preview.html`, `media_preview.html`, `text_preview.html` — Multi-page PDF single-page download/enlarge grid + inline image/audio/video/HTML/text previews
- `static/css/app.css` — Compiled minified Tailwind 3 + DaisyUI 4 CSS (~72.7 KB)
- `static/js/htmx.min.js` — Vendored HTMX 2.0.4
- `static/img/logo.svg` — Converza SVG icon/favicon
- `ui-build/` — PC-only Tailwind/DaisyUI build config
- `tests/` — `test_registry.py`, `test_routes.py`, `test_hardening.py` (41 tests total)

## Completed Work
- **Phases 1–6 & Features**: Core Flask/Waitress backend, tool/policy detection, `PDF → DOCX/HTML/MD/ODT/EPUB`, multi-page PDF single-page download (`Pages (N)`), inline previews + `<dialog>` lightbox, `Popen` cancellation, hardening (`CONVERZA_PASSWORD`, UUID & path guards).
- **UI Rebuild (`CONVERZA_UI_SPEC.md`)**: Rebuilt full frontend and supporting backend routes to match `CONVERZA_UI_SPEC.md` (`converza-dark`/`converza-light` tokens, single `640px` column, sticky header with status dot & icon-only toggle, empty/slim dropzone, unified `file_card.html` with radio format chips & per-card Options, OOB `bulk_bar.html`, `GET /info` bottom sheet, `POST /jobs/<id>/reset`, `toast.html`, `_icons.html` macros, static striped reduced-motion bar, `app.css` 72,749 bytes, `41/41` tests passing).

## Current Work
- UI rebuild complete and verified (`41/41` tests); ready to push to `origin/main` and test on Termux.

## Pending Tasks
- Pull on Termux phone (`git pull`), verify `magick -version` after `pkg upgrade -y`, and verify live mobile UX + 30-minute screen-off stability.

## Known Bugs / Environmental Notes
- On Termux: if `imagemagick` is installed without running `pkg upgrade` first, `libgvc.so` can fail to link `XML_GetCurrentLineNumber64` (fixed by `pkg update && pkg upgrade -y` to update `libexpat`); `_is_working_magick()` ensures broken `magick` binaries do not expose broken UI options.
- On Windows dev PC: `tesseract` and `pdftotext` ran live; `ffmpeg`, `magick`, `pandoc`, and `pdftoppm` are not installed on Windows.
- Live Chrome DevTools visual inspection (`chrome_devtools` MCP) was blocked on the dev PC because Chrome remote debugging (`DevToolsActivePort`) was not enabled.
