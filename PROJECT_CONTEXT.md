# PROJECT_CONTEXT.md

## Project Purpose
Converza is a lightweight, private, self-hosted web file converter (video, audio, image, document, PDF) built with Flask and designed to run on Android via Termux. No accounts, no database, no Docker, no external cloud dependencies.

## Architecture Decisions
- **Strict module separation**:
  - `config.py`: paths (`uploads/`, `outputs/`), upload cap (`500 MB`), TTL (`3600s`), timeout (`900s`).
  - `registry.py`: sole owner of supported categories/targets, CLI tool/policy/OCR-language detection, whitelisted conversion options (`validate_options`), `pdftoppm` multi-page output collection, and `subprocess` argument-list builders (never `shell=True`).
  - `jobs.py`: sole owner of `subprocess` execution (`ThreadPoolExecutor(max_workers=1)`), thread-safe `JOBS` store, multi-page output zipping, bulk ZIP archive assembly, and TTL cleanup thread.
  - `app.py`: HTTP routing, upload/target/option validation, optional `CONVERZA_PASSWORD` Basic Auth gate, security headers, template/partial rendering.
- **No DB / No Redis**: In-memory job store (`JOBS`) protected by `threading.Lock`, single worker thread to prevent phone CPU thermal throttling.
- **Offline-first UI**: Vendored `htmx.min.js` + prebuilt Tailwind CSS 3 / DaisyUI 4 (`static/css/app.css`, compiled on PC).

## Tech Stack
- Python 3.11+, Flask 3.x, Waitress 3.x (`--threads=4`)
- Jinja2 + HTMX 2.0.4 (vendored) + Tailwind CSS 3 + DaisyUI 4 + inline Lucide SVGs
- CLI converters: `ffmpeg`, `magick`/`convert`, `pandoc`, `pdftoppm`/`pdftotext` (Poppler), `tesseract`

## File Structure
- `app.py` — Flask app factory (`create_app()`) and routes (`/`, `/healthz`, `/upload`, `/convert/<id>`, `/convert-all`, `/jobs/<id>` GET/DELETE, `/jobs/<id>/text`, `/download/<id>`, `/zip`, `413` error handler, optional auth gate, security headers)
- `config.py` — Constants and `ensure_dirs()`
- `registry.py` — Categories, targets, labels, cached tool/policy/`ocr_langs` discovery (`get_tools`, `available_targets`), `validate_options()`, `build_cmd()`, `collect_multipage_outputs()`
- `jobs.py` — `is_valid_job_id()`, `create_job()`, `get_job()`, `delete_job()`, `submit()`, `run_job()`, `_finalize_output()`, `build_zip_archive()`, `cleanup_expired()`, `start_cleanup_thread()`, `clear_stale_dirs()`
- `templates/base.html` — Layout, `converza-dark`/`converza-light` theme toggle (`localStorage` + `<meta name="color-scheme">`), Known Limits footer
- `templates/index.html` — Dropzone card, full-window drag-and-drop overlay, clipboard paste (`Ctrl+V`), collapsed **Conversion options** and **Supported formats** `<details>` drawers, `#upload-error`, bulk bar (`>= 2` rows) with Convert all / Download ZIP / Clear done / Clear all, `#files` list, polite live region, LAN-safe Copy handler
- `templates/partials/file_rows.html` — Uploaded rows + soft-tinted skipped-file warning alert + empty notice
- `templates/partials/job_row.html` — Job card partial (`uploaded`, `queued`, `running`, `done`, `error` + Retry, smart non-same default target, `→ Target` badge, `.txt` Preview button, Remove button, OOB swap support)
- `templates/partials/convert_all.html` — Bulk response list of `job_row.html` partials
- `templates/partials/text_preview.html` — Extracted `.txt` / OCR preview (`<= 64 KB`) with accessible Copy button (`command="--copy"`) and `role="status"` feedback
- `static/css/app.css` — Compiled minified Tailwind 3 + DaisyUI 4 CSS
- `static/js/htmx.min.js` — Vendored HTMX 2.0.4
- `ui-build/` — PC-only Tailwind/DaisyUI build config (`package.json`, `package-lock.json`, `tailwind.config.js`, `input.css`)
- `tests/` — `test_registry.py`, `test_routes.py`, `test_hardening.py` (33 tests total)
- `requirements.txt` — `flask`, `waitress`
- `README.md` — Project overview, conversion matrix, Termux & PC dev instructions
- `.gitignore` — Ignores `uploads/`, `outputs/`, `.venv/`, `__pycache__/`, `ui-build/node_modules/`
- `PROJECT_CONTEXT.md` — Persistent project state

## Completed Work
- **Phase 1 (Skeleton)**: Created config, gitignore, requirements, Flask app factory (`/` and `/healthz`), and `.venv`.
- **Phase 2 (Registry & CLI proof)**: Implemented `registry.py` with Windows `convert.exe` collision protection, ImageMagick PDF write policy probe, dynamic `available_targets()`, `build_cmd()`, and `collect_multipage_outputs()`.
- **Phase 3 (Jobs & routes)**: Implemented `jobs.py`, `/upload`, `/convert/<job_id>`, `/jobs/<job_id>`, `/download/<job_id>`, and verified via `unittest` + live `waitress-serve` + `curl.exe`.
- **Phase 4 (UI)**: Built `ui-build/` Tailwind 3 + DaisyUI 4 CSS (`static/css/app.css`), vendored `htmx.min.js` (`2.0.4`), and implemented `base.html`, `index.html`, and styled partials.
- **Phase 5 (Bulk & polish)**: Added `POST /convert-all`, `GET /zip?ids=...` (disk-backed streaming ZIP with cleanup), `413` error handler, Retry recovery, and 5-mixed-file tests.
- **Phase 6 (Hardening)**: Added strict 32-hex `is_valid_job_id()` + `OUTPUT_DIR` `is_relative_to()` path containment checks, `delete_job()` cleanup on failed upload write, `X-Content-Type-Options: nosniff` and `X-Frame-Options: SAMEORIGIN` headers, optional `CONVERZA_PASSWORD` HTTP Basic gate (leaving `/healthz` open), and `tests/test_hardening.py`.
- **UI/UX Polish, Features & Docs**: Contextual right-sidebar options, custom SVG logo + favicon, upload abort + `Popen` process cancellation (`POST /jobs/<id>/cancel`), and multi-step `PDF → HTML / DOCX / MD / ODT / EPUB` pipeline via `pdftohtml` + `pandoc` (`build_steps()` in `registry.py`), verified with `37/37` tests passing.

- **Phase 7 (Termux Verification — Partial Live Pass + Fix)**: Tested live over Wi-Fi (`http://192.168.1.50:5000`): `ffmpeg` (`wav -> mp3`), `tesseract` (`png -> ocr_txt`), `pandoc` (`md -> html`), `pdftotext` (`pdf -> txt`), multi-page `pdftoppm` (`pdf -> png` ZIP), `/convert-all`, and `/zip` all succeeded end-to-end. Caught Termux `magick` linker failure (`CANNOT LINK EXECUTABLE "magick": cannot locate symbol "XML_GetCurrentLineNumber64" referenced by libgvc.so`) when `libexpat` wasn't upgraded; hardened `_find_magick()` via `_is_working_magick()` so broken binaries are hidden rather than offering failing targets (`34/34` tests passing).

## Current Work
- Awaiting `pkg upgrade -y` (to update `libexpat`) + `git pull` on Termux phone, then final `magick` + video conversion + 30-min idle verification.

## Pending Tasks
- On Termux phone: run `pkg update && pkg upgrade -y && magick -version`, `git pull`, restart `waitress-serve` inside `tmux` with `termux-wake-lock`, verify `image -> webp` and `video -> mp4/mp3`, and confirm 30-minute screen-off stability.

## Known Bugs / Environmental Notes
- On Termux: if `imagemagick` is installed without running `pkg upgrade` first, `libgvc.so` can fail to link `XML_GetCurrentLineNumber64` (fixed by `pkg update && pkg upgrade -y` to update `libexpat`); `_is_working_magick()` ensures broken `magick` binaries do not expose broken UI options.
- On Windows dev PC: `tesseract` and `pdftotext` ran live; `ffmpeg`, `magick`, `pandoc`, and `pdftoppm` are not installed on Windows.
- Windows `C:\Windows\system32\convert.exe` is rejected by `_find_magick()`.
- Live Chrome DevTools visual inspection (`chrome_devtools` MCP) was blocked on the dev PC because Chrome remote debugging (`DevToolsActivePort`) was not enabled.

## Important Implementation Details
- `is_valid_job_id()` rejects any non-32-hex ID before `JOBS` lookup; `download()`, `preview_text()`, and `build_zip_archive()` also assert `out_path.resolve().is_relative_to(OUTPUT_DIR.resolve())`.
- `CONVERZA_PASSWORD` environment variable enables Basic Auth (`hmac.compare_digest`) across all routes except `/healthz`; unset by default for local home Wi-Fi usage.
- `GET /jobs/<id>/text` caps preview reads at 64 KB (`65536` chars) for `.txt` outputs only; the Copy button uses `navigator.clipboard.writeText` with a `document.execCommand('copy')` fallback because LAN `http://<phone-ip>:5000` is not a secure context.
