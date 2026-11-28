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
    'pdf': ['png', 'jpg', 'txt', 'html', 'docx', 'md', 'odt', 'epub'],
}

TARGET_LABELS: dict[str, str] = {
    'ocr_txt': 'Text (OCR)',
}

VIDEO_HEIGHTS: dict[str, int | None] = {
    '': None,
    '1080': 1080,
    '720': 720,
    '480': 480,
}

VIDEO_QUALITY_CRF: dict[str, int | None] = {
    '': None,
    'high': 20,
    'balanced': 26,
    'small': 31,
}

AUDIO_BITRATES: dict[str, str | None] = {
    '': None,
    '320': '320k',
    '192': '192k',
    '128': '128k',
    '96': '96k',
    '320k': '320k',
    '192k': '192k',
    '128k': '128k',
    '96k': '96k',
}

IMAGE_WIDTHS: dict[str, int | None] = {
    '': None,
    '1920': 1920,
    '1280': 1280,
    '800': 800,
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


def _is_working_magick(candidate: str | None) -> bool:
    """Return True if candidate exists and runs '-version' as ImageMagick."""
    if not candidate:
        return False
    try:
        res = subprocess.run(
            [candidate, '-version'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = f'{res.stdout}\n{res.stderr}'
        return res.returncode == 0 and 'ImageMagick' in output
    except (OSError, subprocess.SubprocessError):
        return False


def _find_magick() -> str | None:
    """Find a runnable ImageMagick binary, avoiding broken links or Windows convert.exe."""
    for name in ('magick', 'convert'):
        candidate = shutil.which(name)
        if _is_working_magick(candidate):
            return candidate
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


def _ocr_langs(tesseract_bin: str | None) -> list[str]:
    """Return installed Tesseract language codes (always including 'eng' fallback)."""
    if not tesseract_bin:
        return []
    try:
        res = subprocess.run(
            [tesseract_bin, '--list-langs'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = [line.strip() for line in f'{res.stdout}\n{res.stderr}'.splitlines()]
        langs = [
            line for line in lines
            if line and not line.lower().startswith('list of available languages')
            and line.replace('_', '').isalnum()
        ]
        return langs or ['eng']
    except (OSError, subprocess.SubprocessError):
        return ['eng']


@lru_cache(maxsize=1)
def get_tools() -> dict[str, str | bool | list[str] | None]:
    """Discover installed converter binaries and capabilities once."""
    magick_bin = _find_magick()
    tesseract_bin = shutil.which('tesseract')
    return {
        'ffmpeg': shutil.which('ffmpeg'),
        'magick': magick_bin,
        'magick_pdf': _can_magick_write_pdf(magick_bin),
        'tesseract': tesseract_bin,
        'ocr_langs': _ocr_langs(tesseract_bin),
        'pandoc': shutil.which('pandoc'),
        'pdftoppm': shutil.which('pdftoppm'),
        'pdftotext': shutil.which('pdftotext'),
        'pdftohtml': shutil.which('pdftohtml'),
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
        if target == 'html':
            return bool(tools['pdftohtml'])
        if target in ('docx', 'md', 'odt', 'epub'):
            return bool(tools['pdftohtml']) and bool(tools['pandoc'])
        return bool(tools['pdftoppm'])
    return False


def available_targets(category: str) -> list[str]:
    """Return ordered list of targets whose underlying CLI tools are available."""
    if category not in TARGETS:
        return []
    return [t for t in TARGETS[category] if is_target_available(category, t)]


def default_target(category: str, input_ext: str, targets: list[str] | None = None) -> str | None:
    """Return the pre-selected target for an uploaded file per UI spec section 5.4."""
    avail = targets if targets is not None else available_targets(category)
    if not avail:
        return None
    ext = input_ext.lower().lstrip('.')
    preferred: str | None = None
    if category == 'video':
        preferred = 'webm' if ext == 'mp4' else 'mp4'
    elif category == 'pdf':
        preferred = 'png'
    elif category == 'image':
        preferred = 'png' if ext in ('jpg', 'jpeg') else 'jpg'

    if preferred and preferred in avail:
        return preferred
    return next((t for t in avail if t != ext), avail[0])


def engine_statuses() -> list[dict[str, str | bool]]:
    """Return display status rows for each converter engine on this device."""
    tools = get_tools()
    return [
        {'name': 'FFmpeg (video, audio)', 'ready': bool(tools['ffmpeg'])},
        {'name': 'ImageMagick (images)', 'ready': bool(tools['magick'])},
        {'name': 'Pandoc (documents)', 'ready': bool(tools['pandoc'])},
        {'name': 'Poppler (PDF)', 'ready': bool(tools['pdftoppm'] or tools['pdftotext'] or tools['pdftohtml'])},
        {'name': 'Tesseract (OCR)', 'ready': bool(tools['tesseract'])},
    ]


def all_engines_ready() -> bool:
    """Return True if every converter engine is available on this device."""
    return all(bool(row['ready']) for row in engine_statuses())


def validate_options(raw_options: dict | None) -> dict[str, str]:
    """Validate and normalize optional conversion settings against strict whitelists."""
    opts = raw_options or {}
    video_height = str(opts.get('video_size', opts.get('video_height', ''))).strip()
    video_quality = str(opts.get('video_quality', '')).strip().lower()
    audio_bitrate = str(opts.get('audio_bitrate', '')).strip().lower()
    image_quality = str(opts.get('image_quality', '')).strip()
    image_width = str(opts.get('image_width', '')).strip()
    ocr_lang = str(opts.get('ocr_lang', '')).strip()

    if video_height not in VIDEO_HEIGHTS:
        raise ValueError(f'Unsupported video resolution: {video_height}')
    if video_quality not in VIDEO_QUALITY_CRF:
        raise ValueError(f'Unsupported video quality: {video_quality}')
    if audio_bitrate not in AUDIO_BITRATES:
        raise ValueError(f'Unsupported audio bitrate: {audio_bitrate}')
    if image_width not in IMAGE_WIDTHS:
        raise ValueError(f'Unsupported image width: {image_width}')
    if image_quality:
        if not image_quality.isdigit() or not (60 <= int(image_quality) <= 100):
            raise ValueError(f'Unsupported image quality: {image_quality}')

    installed_langs = get_tools().get('ocr_langs') or []
    if ocr_lang and ocr_lang not in installed_langs and ocr_lang != 'eng':
        raise ValueError(f'Unsupported OCR language: {ocr_lang}')

    return {
        'video_height': video_height,
        'video_quality': video_quality,
        'audio_bitrate': audio_bitrate,
        'image_quality': image_quality,
        'image_width': image_width,
        'ocr_lang': ocr_lang,
    }


def build_cmd(
    category: str,
    src: str | Path,
    dst_base: str | Path,
    target: str,
    *,
    require_tool: bool = True,
    options: dict | None = None,
) -> tuple[list[str], str]:
    """Build subprocess argument list and expected output path without shell=True.

    Args:
        category: Validated input file category.
        src: Path to input file.
        dst_base: Output path WITHOUT extension.
        target: Target key from TARGETS[category].
        require_tool: If True, raise RuntimeError when the required tool is missing.
        options: Optional whitelisted quality/resolution/OCR settings.

    Returns:
        Tuple of (cmd_list, expected_output_path).
    """
    if category not in TARGETS or target not in TARGETS[category]:
        raise ValueError(f'Unsupported conversion: {category} -> {target}')

    clean_opts = validate_options(options)
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
        height = VIDEO_HEIGHTS[clean_opts['video_height']]
        crf = VIDEO_QUALITY_CRF[clean_opts['video_quality']]
        bitrate = AUDIO_BITRATES[clean_opts['audio_bitrate']]
        is_audio_out = target in ('mp3', 'wav', 'm4a', 'flac', 'ogg')

        if category == 'video' and is_audio_out:
            cmd.append('-vn')
        if target == 'gif':
            gif_width = 480 if height is None else min(480, height)
            cmd.extend(['-vf', f'fps=10,scale={gif_width}:-1'])
        elif category == 'video' and not is_audio_out:
            if height is not None:
                cmd.extend(['-vf', f'scale=-2:{height}'])
            if crf is not None and target in ('mp4', 'mkv'):
                cmd.extend(['-crf', str(crf)])

        if bitrate and target in ('mp3', 'm4a', 'ogg'):
            cmd.extend(['-b:a', bitrate])

        cmd.append(out)
        return cmd, out

    if category == 'image':
        if target == 'ocr_txt':
            tesseract = str(tools['tesseract'] or 'tesseract')
            cmd = [tesseract, src_str, dst_str]
            if clean_opts['ocr_lang']:
                cmd.extend(['-l', clean_opts['ocr_lang']])
            return cmd, out
        magick = str(tools['magick'] or 'magick')
        quality_str = clean_opts['image_quality']
        width = IMAGE_WIDTHS[clean_opts['image_width']]
        cmd = [magick, src_str]
        if width is not None:
            cmd.extend(['-resize', f'{width}x'])
        if quality_str and target in ('jpg', 'webp'):
            cmd.extend(['-quality', quality_str])
        cmd.append(out)
        return cmd, out

    if category == 'document':
        pandoc = str(tools['pandoc'] or 'pandoc')
        return [pandoc, src_str, '-o', out], out

    if category == 'pdf':
        if target == 'txt':
            pdftotext = str(tools['pdftotext'] or 'pdftotext')
            return [pdftotext, src_str, out], out
        if target == 'html':
            pdftohtml = str(tools['pdftohtml'] or 'pdftohtml')
            stage_base = f'{dst_str}_stage'
            return [pdftohtml, '-s', '-i', '-noframes', src_str, stage_base], f'{stage_base}-html.html'
        if target in ('docx', 'md', 'odt', 'epub'):
            raise ValueError('Multi-step PDF document targets must use build_steps()')
        pdftoppm = str(tools['pdftoppm'] or 'pdftoppm')
        flag = '-png' if target == 'png' else '-jpeg'
        return [pdftoppm, flag, src_str, dst_str], out

    raise ValueError(f'Unsupported category: {category}')


def build_steps(
    category: str,
    src: str | Path,
    dst_base: str | Path,
    target: str,
    *,
    require_tool: bool = True,
    options: dict | None = None,
) -> tuple[list[list[str]], str]:
    """Build one or more sequential subprocess argument lists for a conversion."""
    if category == 'pdf' and target in ('docx', 'md', 'odt', 'epub'):
        if require_tool and not is_target_available(category, target):
            raise RuntimeError(f'Required converter tool is not available for {category} -> {target}')
        tools = get_tools()
        pdftohtml = str(tools['pdftohtml'] or 'pdftohtml')
        pandoc = str(tools['pandoc'] or 'pandoc')
        stage_base = f'{dst_base}_stage'
        stage_html = f'{stage_base}-html.html'
        out = f'{dst_base}.{target}'
        return (
            [
                [pdftohtml, '-s', '-i', '-noframes', str(src), stage_base],
                [pandoc, stage_html, '-o', out],
            ],
            out,
        )
    cmd, out = build_cmd(
        category,
        src,
        dst_base,
        target,
        require_tool=require_tool,
        options=options,
    )
    return [cmd], out


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
