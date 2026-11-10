"""Profile-owned artifact downloads, independent of the host workspace file door.

Only packet-manifest PDFs and recorded teacher originals are eligible. This is
not a general filesystem reader, even when an output directory is customized.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from . import curriculum
from .packet import key_coverage
from .panel import PanelError, resolve_packet_file
from .tools import Runtime

MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
_TYPES = {'.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg',
          '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif',
          '.heic': 'image/heic', '.heif': 'image/heif', '.txt': 'text/plain',
          '.md': 'text/markdown'}


def _packet_reference(rt: Runtime, target: Path) -> bool:
    root = rt.store.packets_root.resolve()
    if not target.is_relative_to(root):
        return False
    relative = target.relative_to(root)
    if len(relative.parts) != 2 or target.suffix.lower() != '.pdf':
        return False
    try:
        candidate = resolve_packet_file(rt, relative.parts[0], relative.parts[1])
        data = json.loads((candidate.parent / 'packet.json').read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not isinstance(data.get('children'), dict):
            return False
        files = data.get('files', {})
        names = set(files.values()) if isinstance(files, dict) else set()
        names.update(key_coverage(data))
        return candidate == target and target.name in names
    except (OSError, ValueError, TypeError, PanelError):
        return False


def _material_reference(rt: Runtime, target: Path) -> bool:
    root = (rt.store.root / 'children').resolve()
    if not target.is_relative_to(root):
        return False
    parts = target.relative_to(root).parts
    if len(parts) < 2:
        return False
    child_id = parts[0]
    try:
        child_root = rt.store.child_dir(child_id).resolve()
        return target.is_relative_to(child_root) and any(
            row.get('file') and Path(row['file']).resolve() == target
            for row in curriculum.materials(rt.store, child_id)
        )
    except (OSError, ValueError, TypeError):
        return False


def artifact_download(rt: Runtime, requested: object) -> dict:
    if not isinstance(requested, str) or not requested.strip() or len(requested) > 4096:
        raise PanelError('An artifact path is required.')
    path = Path(requested)
    if not path.is_absolute():
        raise PanelError('Download requires the absolute artifact path returned by Homework Coach.')
    try:
        target = path.resolve(strict=True)
        if not target.is_file() or target.suffix.lower() not in _TYPES:
            raise PanelError('This file is not a downloadable Homework Coach artifact.')
        if not (_packet_reference(rt, target) or _material_reference(rt, target)):
            raise PanelError('This file is not a recorded artifact in the selected profile.')
        if target.stat().st_size > MAX_DOWNLOAD_BYTES:
            raise PanelError('Direct download is limited to 25 MiB; use the host file download for larger files.')
        # Bound the read as well as stat, in case a file grows between the checks.
        with target.open('rb') as stream:
            content = stream.read(MAX_DOWNLOAD_BYTES + 1)
        if len(content) > MAX_DOWNLOAD_BYTES:
            raise PanelError('The artifact exceeds the 25 MiB direct-download limit.')
    except OSError as exc:
        raise PanelError('The recorded artifact is no longer available.') from exc
    return {'name': target.name, 'content_type': _TYPES[target.suffix.lower()],
            'size': len(content), 'data_b64': base64.b64encode(content).decode('ascii')}
