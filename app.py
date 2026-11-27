from __future__ import annotations

import hmac
import os
import re
from pathlib import Path

from flask import Flask, Response, abort, render_template, request, send_file
from werkzeug.utils import secure_filename

from config import MAX_UPLOAD_MB, OUTPUT_DIR, UPLOAD_DIR, ensure_dirs
import jobs
import registry

_CTRL_RE = re.compile(r'[\x00-\x1f\x7f]')


def _format_size(num_bytes: int) -> str:
    """Format byte size into a compact human-readable string."""
    size = float(max(0, num_bytes or 0))
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024.0 or unit == 'GB':
            return f'{int(size)} B' if unit == 'B' else f'{size:.1f} {unit}'
        size /= 1024.0
    return f'{int(num_bytes)} B'


def _parse_upload_name(raw_filename: str) -> tuple[str, str]:
    """Extract sanitized display filename and normalized extension without breaking Unicode."""
    normalized = (raw_filename or '').replace('\\', '/')
    base = _CTRL_RE.sub('', Path(normalized).name).strip()
    ext = Path(base).suffix.lstrip('.').lower()
    if not base:
        return '', ''
    return base, ext


def _row_context(job: dict) -> dict:
    """Attach available target list, smart default target, and preview flag."""
    targets = registry.available_targets(job['category'])
    default_target = job.get('target')
    if not default_target and targets:
        default_target = next((t for t in targets if t != job['ext']), targets[0])
    out_val = job.get('output') or ''
    can_preview_text = job['status'] == 'done' and out_val.lower().endswith('.txt')
    return {
        **job,
        'targets': targets,
        'default_target': default_target,
        'can_preview_text': can_preview_text,
    }


def _extract_options(form) -> dict[str, str]:
    """Read optional conversion settings from submitted form data."""
    return {
        'video_height': form.get('video_height', ''),
        'audio_bitrate': form.get('audio_bitrate', ''),
        'image_quality': form.get('image_quality', ''),
        'ocr_lang': form.get('ocr_lang', ''),
    }


def _capabilities() -> list[dict]:
    """Return active categories, accepted input extensions, and available targets."""
    caps: list[dict] = []
    for cat, exts in registry.CATEGORIES.items():
        targets = registry.available_targets(cat)
        if targets:
            caps.append({
                'category': cat,
                'inputs': sorted(exts),
                'targets': [registry.target_label(t) for t in targets],
            })
    return caps


def _parse_bulk_targets(form) -> list[tuple[str, str]]:
    """Extract (job_id, target) pairs from target_<id> or paired job_id/target fields."""
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()

    for key, value in form.items():
        if key.startswith('target_'):
            jid = key.removeprefix('target_').strip()
            target = value.strip()
            if jid and jid not in seen:
                seen.add(jid)
                pairs.append((jid, target))

    for jid, target in zip(form.getlist('job_id'), form.getlist('target')):
        clean_id = jid.strip()
        if clean_id and clean_id not in seen:
            seen.add(clean_id)
            pairs.append((clean_id, target.strip()))

    return pairs


def create_app(*, start_cleanup: bool = True, clean_on_start: bool = True) -> Flask:
    """Create and configure the Converza Flask application."""
    ensure_dirs()
    if clean_on_start:
        jobs.clear_stale_dirs()
    if start_cleanup:
        jobs.start_cleanup_thread()

    application = Flask(__name__)
    application.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_MB * 1024 * 1024
    application.jinja_env.filters['format_size'] = _format_size
    application.jinja_env.globals['target_label'] = registry.target_label

    @application.before_request
    def optional_password_gate():
        password = os.environ.get('CONVERZA_PASSWORD', '')
        if not password or request.path == '/healthz':
            return None
        auth = request.authorization
        if not auth or not hmac.compare_digest(auth.password or '', password):
            return Response(
                'Authentication required',
                401,
                {'WWW-Authenticate': 'Basic realm="Converza"'},
            )
        return None

    @application.after_request
    def security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        return response

    @application.errorhandler(413)
    def file_too_large(_err):
        html = (
            f'<div class="alert alert-error rounded-xl text-sm" role="alert">'
            f'<span>Upload exceeds the {MAX_UPLOAD_MB} MB size limit.</span>'
            f'</div>'
        )
        return html, 413

    @application.get('/')
    def index():
        return render_template(
            'index.html',
            max_upload_mb=MAX_UPLOAD_MB,
            capabilities=_capabilities(),
            tools=registry.get_tools(),
        )

    @application.get('/healthz')
    def healthz():
        return 'ok', 200, {'Content-Type': 'text/plain; charset=utf-8'}

    @application.post('/upload')
    def upload():
        rows: list[dict] = []
        skipped: list[str] = []
        raw_files = [f for f in request.files.getlist('files') if (f.filename or '').strip()]

        for storage in raw_files:
            display_name, ext = _parse_upload_name(storage.filename or '')
            if not display_name:
                continue
            category = registry.detect_category(ext)
            targets = registry.available_targets(category) if category else []
            if not category or not targets:
                skipped.append(display_name)
                continue

            job, in_path = jobs.create_job(display_name, category, ext)
            try:
                storage.save(in_path)
            except OSError:
                jobs.delete_job(job['id'], allow_active=True)
                abort(500)
            size = in_path.stat().st_size if in_path.is_file() else 0
            jobs.set_size(job['id'], size)
            job['size'] = size
            rows.append(_row_context(job))

        return render_template(
            'partials/file_rows.html',
            rows=rows,
            skipped=skipped,
            empty=not raw_files,
        )

    @application.post('/convert/<job_id>')
    def convert(job_id: str):
        job = jobs.get_job(job_id) or abort(404)
        target = request.form.get('target', '').strip()
        if not registry.is_target_available(job['category'], target):
            abort(400)

        src = UPLOAD_DIR / job_id / f"in.{job['ext']}"
        dst_base = OUTPUT_DIR / job_id / 'out'
        try:
            options = registry.validate_options(_extract_options(request.form))
        except ValueError:
            abort(400)
        steps, out = registry.build_steps(job['category'], src, dst_base, target, options=options)
        updated, err = jobs.submit(job_id, steps, out, target)
        if err == 'not_found' or updated is None:
            abort(404)
        status_code = 409 if err == 'already_active' else 200
        return render_template('partials/job_row.html', job=_row_context(updated)), status_code

    @application.post('/convert-all')
    def convert_all():
        pairs = _parse_bulk_targets(request.form)
        if not pairs:
            abort(400)

        queued_rows: list[dict] = []
        pending_specs: list[tuple[dict, list[str], str, str]] = []
        matched_any = False

        try:
            options = registry.validate_options(_extract_options(request.form))
        except ValueError:
            abort(400)

        for jid, target in pairs:
            job = jobs.get_job(jid)
            if job is None:
                continue
            matched_any = True
            if job['status'] not in ('uploaded', 'error'):
                continue
            if not registry.is_target_available(job['category'], target):
                abort(400)
            src = UPLOAD_DIR / jid / f"in.{job['ext']}"
            dst_base = OUTPUT_DIR / jid / 'out'
            steps, out = registry.build_steps(job['category'], src, dst_base, target, options=options)
            pending_specs.append((job, steps, out, target))

        if not matched_any:
            abort(404)

        for job, cmd, out, target in pending_specs:
            updated, err = jobs.submit(job['id'], cmd, out, target)
            if updated is not None and err != 'not_found':
                queued_rows.append(_row_context(updated))

        is_htmx = request.headers.get('HX-Request') == 'true'
        return render_template('partials/convert_all.html', rows=queued_rows, oob=is_htmx)

    @application.get('/jobs/<job_id>')
    def job_status(job_id: str):
        job = jobs.get_job(job_id) or abort(404)
        return render_template('partials/job_row.html', job=_row_context(job))

    @application.get('/jobs/<job_id>/text')
    def preview_text(job_id: str):
        job = jobs.get_job(job_id) or abort(404)
        if job['status'] != 'done' or not job['output']:
            abort(404)
        out_path = Path(job['output']).resolve()
        if (
            not out_path.is_relative_to(OUTPUT_DIR.resolve())
            or out_path.suffix.lower() != '.txt'
            or not out_path.is_file()
        ):
            abort(404)
        raw = out_path.read_text(encoding='utf-8', errors='replace')
        truncated = len(raw) > 65536
        text = raw[:65536]
        return render_template(
            'partials/text_preview.html',
            job=job,
            text=text,
            truncated=truncated,
        )

    @application.delete('/jobs/<job_id>')
    def remove_job(job_id: str):
        deleted, reason = jobs.delete_job(job_id)
        if not deleted:
            abort(409 if reason == 'active' else 404)
        return '', 200

    @application.post('/jobs/<job_id>/cancel')
    def cancel_job_route(job_id: str):
        updated, err = jobs.cancel_job(job_id)
        if err == 'not_found' or updated is None:
            abort(404)
        status_code = 409 if err == 'not_active' else 200
        return render_template('partials/job_row.html', job=_row_context(updated)), status_code

    @application.get('/download/<job_id>')
    def download(job_id: str):
        job = jobs.get_job(job_id) or abort(404)
        if job['status'] != 'done' or not job['output']:
            abort(404)
        out_path = Path(job['output']).resolve()
        if not out_path.is_relative_to(OUTPUT_DIR.resolve()) or not out_path.is_file():
            abort(404)
        stem = secure_filename(Path(job['name']).stem) or 'converted'
        return send_file(
            out_path,
            as_attachment=True,
            download_name=f'{stem}{out_path.suffix}',
        )

    @application.get('/zip')
    def download_zip():
        raw_ids = request.args.get('ids', '')
        job_ids: list[str] = []
        seen: set[str] = set()
        for part in raw_ids.split(','):
            jid = part.strip()
            if jid and jid not in seen:
                seen.add(jid)
                job_ids.append(jid)
        if not job_ids:
            abort(400)

        try:
            zip_path = jobs.build_zip_archive(job_ids)
        except (LookupError, FileNotFoundError):
            abort(404)

        zip_size = zip_path.stat().st_size

        def _stream_and_delete():
            try:
                with zip_path.open('rb') as fh:
                    while True:
                        chunk = fh.read(65536)
                        if not chunk:
                            break
                        yield chunk
            finally:
                zip_path.unlink(missing_ok=True)

        return Response(
            _stream_and_delete(),
            mimetype='application/zip',
            headers={
                'Content-Disposition': 'attachment; filename="converza_files.zip"',
                'Content-Length': str(zip_size),
            },
        )

    return application


app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
