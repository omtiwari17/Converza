# Converza

A lightweight, private, self-hosted file converter built with Flask, Waitress, HTMX, and Tailwind CSS / DaisyUI. Designed to run on an Android phone via **Termux** (or any PC/server on your local network) with no database, no Docker, no accounts, and no files leaving your device.

## Supported Conversions

| Category | Input formats | Output targets | CLI tool |
|---|---|---|---|
| **Video** | `mp4`, `mkv`, `avi`, `mov`, `webm` | `mp4`, `mkv`, `webm`, `gif`, `mp3`, `wav`, `m4a` | `ffmpeg` |
| **Audio** | `mp3`, `wav`, `flac`, `ogg`, `m4a`, `aac` | `mp3`, `wav`, `flac`, `ogg`, `m4a` | `ffmpeg` |
| **Image** | `png`, `jpg`, `jpeg`, `webp`, `gif`, `bmp`, `tiff` | `png`, `jpg`, `webp`, `gif`, `bmp`, `tiff`, `pdf`, `Text (OCR)` | `magick` / `convert`, `tesseract` |
| **Document** | `md`, `html`, `docx`, `odt`, `epub`, `txt`, `rst` | `md`, `html`, `docx`, `odt`, `epub`, `txt` | `pandoc` |
| **PDF** | `pdf` | `png`, `jpg`, `txt` | `pdftoppm`, `pdftotext` |

Missing tools and restricted ImageMagick PDF policies are detected at startup and automatically hidden in the UI. Multi-page PDF renders (`png`/`jpg`) are bundled into a `.zip` automatically.

## Features

- Multi-file upload via tap or drag-and-drop with smart default target selection
- Sequential background worker (`ThreadPoolExecutor(max_workers=1)`) to protect phone CPU/thermals
- Live 1-second HTMX polling, single-file download, bulk **Convert all**, **Download all (ZIP)**, **Clear done**, and **Retry** on errors
- Dark and light themes (`data-theme` saved in `localStorage`) with offline vendored `htmx.min.js` and pre-built `static/css/app.css`
- Auto-cleanup after 1 hour (`JOB_TTL_SECONDS = 3600`) and stale directory sweep on startup

## Termux Setup (Android)

Keep the repository in Termux's home directory (`~`), not shared storage (`/sdcard`), and disable Android battery optimization for Termux.

```bash
pkg update && pkg upgrade
pkg install python ffmpeg imagemagick pandoc poppler tesseract tmux git

git clone https://github.com/omtiwari17/Converza.git converza
cd converza
pip install -r requirements.txt

# Verify installed converter tools
ffmpeg -version
magick -version || convert -version
pandoc -v
pdftoppm -v
tesseract --version

# Keep CPU awake and run in tmux
termux-wake-lock
tmux new -s converza
waitress-serve --host=0.0.0.0 --port=5000 --threads=4 app:app
```

Open `http://<phone-ip>:5000` from any device on the same Wi-Fi (`ip addr` shows your phone's IP).

## Local PC Development & Tests

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run unit, route, and hardening tests
python -m unittest discover -s tests -v

# Start local server
waitress-serve --host=127.0.0.1 --port=5000 --threads=4 app:app
```

### Rebuilding CSS (PC only, optional)

Termux does not need Node.js because the compiled stylesheet is committed at `static/css/app.css`. To rebuild after editing templates or `ui-build/input.css`:

```bash
cd ui-build
npm install
npm run build
```

## Configuration & Security

Limits in `config.py`:

- `MAX_UPLOAD_MB = 500`
- `JOB_TTL_SECONDS = 3600` (1 hour)
- `CONVERT_TIMEOUT = 900` (15 minutes per conversion)

If you expose Converza beyond your home Wi-Fi (prefer Tailscale or a private tunnel), set `CONVERZA_PASSWORD` to require HTTP Basic authentication across all routes except `/healthz`:

```bash
export CONVERZA_PASSWORD="your-strong-password"
waitress-serve --host=0.0.0.0 --port=5000 --threads=4 app:app
```

## Project Structure

```text
Converza/
├── app.py                  # Flask routes, upload validation, optional auth, headers
├── config.py               # Paths, upload size limit, TTL, timeout constants
├── registry.py             # Format map, tool/policy detection, CLI command builders
├── jobs.py                 # Single-worker executor, job state, ZIP builder, TTL cleanup
├── templates/              # base.html, index.html, and HTMX partials
├── static/
│   ├── css/app.css         # Pre-built minified Tailwind CSS 3 + DaisyUI 4
│   └── js/htmx.min.js      # Vendored HTMX 2.0.4
├── ui-build/               # PC-only Tailwind/DaisyUI build configuration
├── tests/                  # Registry, routes, and Section 12 hardening tests
├── requirements.txt        # Flask and Waitress
└── PROJECT_CONTEXT.md      # Phase log and architecture notes
```

## Known Limits

- No Word/Excel/PowerPoint to PDF, no Markdown or Word to PDF, and no `mobi`/`azw3` ebook conversions.
- Large videos convert slowly on mobile CPUs; conversions run one at a time.
- Job metadata lives in memory; restarting the server clears active/finished job entries and cleans temporary files.
