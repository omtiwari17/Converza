from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from werkzeug.utils import secure_filename

from config import CONVERT_TIMEOUT, JOB_TTL_SECONDS, OUTPUT_DIR, UPLOAD_DIR
import registry

JOBS: dict[str, dict] = {}
LOCK = threading.Lock()
POOL = ThreadPoolExecutor(max_workers=1)
_CLEANUP_STARTED = False
_CLEANUP_LOCK = threading.Lock()


def is_valid_job_id(job_id: str) -> bool:
    """Return True if job_id is a well-formed 32-char lowercase hex UUID."""
    return len(job_id) == 32 and all(ch in '0123456789abcdef' for ch in job_id)


def clear_stale_dirs() -> None:
    """Remove leftover upload/output directories from prior runs."""
    for root in (UPLOAD_DIR, OUTPUT_DIR):
        if not root.exists():
            continue
        for entry in root.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)


def create_job(orig_name: str, category: str, ext: str, size: int = 0) -> tuple[dict, Path]:
    """Allocate UUID directories, register a new uploaded job, and return (snapshot, input_path)."""
    job_id = uuid.uuid4().hex
    up_dir = UPLOAD_DIR / job_id
    out_dir = OUTPUT_DIR / job_id
    up_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    record = {
        'id': job_id,
        'name': orig_name,
        'category': category,
        'ext': ext,
        'size': size,
        'target': None,
        'status': 'uploaded',
        'error': None,
        'output': None,
        'created': time.time(),
    }
    with LOCK:
        JOBS[job_id] = record
        snapshot = dict(record)
    return snapshot, up_dir / f'in.{ext}'


def set_size(job_id: str, size: int) -> None:
    """Update the byte size recorded for an uploaded job."""
    with LOCK:
        if job_id in JOBS:
            JOBS[job_id]['size'] = size


def get_job(job_id: str) -> dict | None:
    """Return a thread-safe copy of a job record, or None if not found."""
    if not is_valid_job_id(job_id):
        return None
    with LOCK:
        job = JOBS.get(job_id)
        return dict(job) if job is not None else None


def delete_job(job_id: str) -> None:
    """Remove a job record and its upload/output directories (e.g. failed upload save)."""
    if not is_valid_job_id(job_id):
        return
    with LOCK:
        JOBS.pop(job_id, None)
    shutil.rmtree(UPLOAD_DIR / job_id, ignore_errors=True)
    shutil.rmtree(OUTPUT_DIR / job_id, ignore_errors=True)


def _clear_job_outputs(job_id: str) -> None:
    """Remove any prior output files before retrying a conversion."""
    out_dir = OUTPUT_DIR / job_id
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)


def _finalize_output(job_id: str, category: str, target: str, out_path: str | Path) -> Path:
    """Resolve single or multi-page outputs into the final deliverable path."""
    if registry.is_multipage_target(category, target):
        dst_base = OUTPUT_DIR / job_id / 'out'
        pages = registry.collect_multipage_outputs(dst_base, target)
        if not pages:
            raise RuntimeError('No pages were generated from PDF')
        if len(pages) == 1:
            return pages[0]
        zip_path = OUTPUT_DIR / job_id / 'out.zip'
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for page in pages:
                zf.write(page, arcname=page.name)
        return zip_path

    final_path = Path(out_path)
    if not final_path.is_file():
        raise RuntimeError('Converter finished without creating an output file')
    return final_path


def run_job(job_id: str, cmd: list[str], out_path: str | Path, category: str, target: str) -> None:
    """Execute one conversion command in the worker thread and update job state."""
    with LOCK:
        if job_id not in JOBS:
            return
        JOBS[job_id]['status'] = 'running'

    try:
        subprocess.run(cmd, check=True, timeout=CONVERT_TIMEOUT, capture_output=True)
        final_out = _finalize_output(job_id, category, target, out_path)
        with LOCK:
            if job_id in JOBS:
                JOBS[job_id].update(status='done', output=str(final_out), error=None)
    except subprocess.TimeoutExpired:
        with LOCK:
            if job_id in JOBS:
                JOBS[job_id].update(status='error', error='Timed out', output=None)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b'').decode(errors='ignore').strip()
        stdout = (exc.stdout or b'').decode(errors='ignore').strip()
        msg = (stderr or stdout or 'Conversion failed')[-300:]
        with LOCK:
            if job_id in JOBS:
                JOBS[job_id].update(status='error', error=msg, output=None)
    except (OSError, RuntimeError) as exc:
        with LOCK:
            if job_id in JOBS:
                JOBS[job_id].update(status='error', error=str(exc)[-300:], output=None)


def submit(job_id: str, cmd: list[str], out_path: str | Path, target: str) -> tuple[dict | None, str | None]:
    """Queue a job for conversion. Returns (job_snapshot, error_code)."""
    with LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return None, 'not_found'
        if job['status'] in ('queued', 'running'):
            return dict(job), 'already_active'
        category = job['category']
        _clear_job_outputs(job_id)
        job.update(target=target, status='queued', error=None, output=None)
        snapshot = dict(job)

    POOL.submit(run_job, job_id, cmd, out_path, category, target)
    return snapshot, None


def cleanup_expired(ttl_seconds: int = JOB_TTL_SECONDS) -> int:
    """Delete expired jobs and their upload/output directories. Returns deleted count."""
    cutoff = time.time() - ttl_seconds
    with LOCK:
        expired = [
            jid for jid, job in JOBS.items()
            if job['created'] < cutoff and job['status'] != 'running'
        ]
        for jid in expired:
            del JOBS[jid]

    for jid in expired:
        shutil.rmtree(UPLOAD_DIR / jid, ignore_errors=True)
        shutil.rmtree(OUTPUT_DIR / jid, ignore_errors=True)
    return len(expired)


def cleanup_loop() -> None:
    """Periodically remove jobs older than JOB_TTL_SECONDS."""
    while True:
        time.sleep(300)
        cleanup_expired()


def start_cleanup_thread() -> None:
    """Start the background TTL cleanup daemon once per process."""
    global _CLEANUP_STARTED
    with _CLEANUP_LOCK:
        if _CLEANUP_STARTED:
            return
        threading.Thread(target=cleanup_loop, daemon=True, name='converza-cleanup').start()
        _CLEANUP_STARTED = True


def build_zip_archive(job_ids: list[str]) -> Path:
    """Bundle finished job outputs into a temporary ZIP file on disk.

    Raises LookupError if any job is missing or not finished, or FileNotFoundError
    if an output file no longer exists on disk.
    """
    entries: list[tuple[Path, str]] = []
    seen_names: dict[str, int] = {}

    for jid in job_ids:
        job = get_job(jid)
        if job is None or job['status'] != 'done' or not job['output']:
            raise LookupError(jid)
        out_path = Path(job['output']).resolve()
        if not out_path.is_relative_to(OUTPUT_DIR.resolve()):
            raise LookupError(jid)
        if not out_path.is_file():
            raise FileNotFoundError(jid)

        stem = secure_filename(Path(job['name']).stem) or 'converted'
        ext = out_path.suffix
        base_name = f'{stem}{ext}'
        count = seen_names.get(base_name, 0) + 1
        seen_names[base_name] = count
        arcname = base_name if count == 1 else f'{stem}_{count}{ext}'
        entries.append((out_path, arcname))

    fd, tmp_name = tempfile.mkstemp(prefix='converza_', suffix='.zip')
    os.close(fd)
    zip_path = Path(tmp_name)
    try:
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for src_path, arcname in entries:
                zf.write(src_path, arcname=arcname)
    except Exception:
        zip_path.unlink(missing_ok=True)
        raise
    return zip_path

