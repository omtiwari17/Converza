from __future__ import annotations

import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

CATEGORIES: dict[str, set[str]] = {
    'video': {'mp4', 'mkv', 'avi', 'mov', 'webm'},
    'audio': {'mp3', 'wav', 'flac', 'ogg', 'm4a', 'aac'},
    'image': {'png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'tiff'},
    'document': {'md', 'html', 'docx', 'odt', 'epub', 'txt', 'rst'},
    'pdf': {'pdf'},
}

TARGETS: dict[str, list[str]] = {
    'video': ['mp4', 'mkv', 'webm', 'gif', 'mp3', 'wav', 'm4a'],
    'audio': ['mp3', 'wav', 'flac', 'ogg', 'm4a'],
    'image': ['png', 'jpg', 'webp', 'gif', 'bmp', 'tiff', 'pdf', 'ocr_txt'],
    'document': ['md', 'html', 'docx', 'odt', 'epub', 'txt'],
    'pdf': ['png', 'jpg', 'txt'],
}

TARGET_LABELS: dict[str, str] = {
    'ocr_txt': 'Text (OCR)',
}


def target_label(target: str) -> str:
    """Return the user-facing display label for a conversion target."""
    return TARGET_LABELS.get(target, target.upper())


def detect_category(ext: str) -> str | None:
    """Return the category name for a file extension, or None if unsupported."""
    clean = ext.lower().lstrip('.')
    if not clean:
        return None
    for cat, exts in CATEGORIES.items():
        if clean in exts:
            return cat
    return None


def _find_magick() -> str | None:
    """Find ImageMagick binary, avoiding Windows system32 convert.exe collision."""
    magick = shutil.which('magick')
    if magick:
        return magick
    convert = shutil.which('convert')
    if not convert:
        return None
    try:
        res = subprocess.run(
            [convert, '-version'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = f'{res.stdout}\n{res.stderr}'
        if 'ImageMagick' in output:
            return convert
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def _can_magick_write_pdf(magick_bin: str | None) -> bool:
    """Check whether ImageMagick permits writing PDF files (policy/delegates)."""
    if not magick_bin:
        return False
    try:
        with tempfile.TemporaryDirectory() as tmp:
            probe_pdf = Path(tmp) / 'probe.pdf'
            res = subprocess.run(
                [magick_bin, 'xc:white', '-resize', '1x1!', f'pdf:{probe_pdf}'],
                capture_output=True,
                timeout=10,
            )
            return res.returncode == 0 and probe_pdf.is_file() and probe_pdf.stat().st_size > 0
    except (OSError, subprocess.SubprocessError):
        return False


@lru_cache(maxsize=1)
def get_tools() -> dict[str, str | bool | None]:
    """Discover installed converter binaries and capabilities once."""
    magick_bin = _find_magick()
    return {
        'ffmpeg': shutil.which('ffmpeg'),
        'magick': magick_bin,
        'magick_pdf': _can_magick_write_pdf(magick_bin),
        'tesseract': shutil.which('tesseract'),
        'pandoc': shutil.which('pandoc'),
        'pdftoppm': shutil.which('pdftoppm'),
        'pdftotext': shutil.which('pdftotext'),
    }


def refresh_tools() -> dict[str, str | bool | None]:
    """Clear cached tool discovery and re-detect installed binaries."""
    get_tools.cache_clear()
    return get_tools()


def is_target_available(category: str, target: str) -> bool:
    """Return True if the target is valid for the category and its tool is installed."""
    if category not in TARGETS or target not in TARGETS[category]:
        return False
    tools = get_tools()
    if category in ('video', 'audio'):
        return bool(tools['ffmpeg'])
    if category == 'image':
        if target == 'ocr_txt':
            return bool(tools['tesseract'])
        if target == 'pdf':
            return bool(tools['magick']) and bool(tools['magick_pdf'])
        return bool(tools['magick'])
    if category == 'document':
        return bool(tools['pandoc'])
    if category == 'pdf':
        if target == 'txt':
            return bool(tools['pdftotext'])
        return bool(tools['pdftoppm'])
    return False


def available_targets(category: str) -> list[str]:
    """Return ordered list of targets whose underlying CLI tools are available."""
    if category not in TARGETS:
        return []
    return [t for t in TARGETS[category] if is_target_available(category, t)]


def build_cmd(
    category: str,
    src: str | Path,
    dst_base: str | Path,
    target: str,
    *,
    require_tool: bool = True,
) -> tuple[list[str], str]:
    """Build subprocess argument list and expected output path without shell=True.

    Args:
        category: Validated input file category.
        src: Path to input file.
        dst_base: Output path WITHOUT extension.
        target: Target key from TARGETS[category].
        require_tool: If True, raise RuntimeError when the required tool is missing.

    Returns:
        Tuple of (cmd_list, expected_output_path).
    """
    if category not in TARGETS or target not in TARGETS[category]:
        raise ValueError(f'Unsupported conversion: {category} -> {target}')

    tools = get_tools()
    if require_tool and not is_target_available(category, target):
        raise RuntimeError(f'Required converter tool is not available for {category} -> {target}')

    src_str = str(src)
    dst_str = str(dst_base)
    ext = 'txt' if target == 'ocr_txt' else target
    out = f'{dst_str}.{ext}'

    if category in ('video', 'audio'):
        ffmpeg = str(tools['ffmpeg'] or 'ffmpeg')
        cmd = [ffmpeg, '-y', '-i', src_str]
        if category == 'video' and target in ('mp3', 'wav', 'm4a'):
            cmd.append('-vn')
        if target == 'gif':
            cmd.extend(['-vf', 'fps=10,scale=480:-1'])
        cmd.append(out)
        return cmd, out

    if category == 'image':
        if target == 'ocr_txt':
            tesseract = str(tools['tesseract'] or 'tesseract')
            return [tesseract, src_str, dst_str], out
        magick = str(tools['magick'] or 'magick')
        return [magick, src_str, out], out

    if category == 'document':
        pandoc = str(tools['pandoc'] or 'pandoc')
        return [pandoc, src_str, '-o', out], out

    if category == 'pdf':
        if target == 'txt':
            pdftotext = str(tools['pdftotext'] or 'pdftotext')
            return [pdftotext, src_str, out], out
        pdftoppm = str(tools['pdftoppm'] or 'pdftoppm')
        flag = '-png' if target == 'png' else '-jpeg'
        return [pdftoppm, flag, src_str, dst_str], out

    raise ValueError(f'Unsupported category: {category}')


def is_multipage_target(category: str, target: str) -> bool:
    """Return True when the tool emits numbered page files instead of a single output."""
    return category == 'pdf' and target in ('png', 'jpg')


def collect_multipage_outputs(dst_base: str | Path, target: str) -> list[Path]:
    """Return generated page files sorted in natural page order for pdftoppm."""
    base_path = Path(dst_base)
    pattern = f'{base_path.name}-*.{target}'
    files = list(base_path.parent.glob(pattern))

    def _page_key(path: Path) -> tuple[int, str]:
        suffix = path.stem.removeprefix(f'{base_path.name}-')
        return (int(suffix), path.name) if suffix.isdigit() else (0, path.name)

    return sorted(files, key=_page_key)
